import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI(title="Partyka Solver API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "penalty_config.json"
VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python"

# --- Models ---
class ConfigUpdate(BaseModel):
    ladder: List[str]
    penalty_ratio: float
    effort_threshold: float
    time_limit_seconds: float

class StartSearchRequest(BaseModel):
    time_limit: float

# --- Helpers ---
def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config: Dict[str, Any]):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

async def run_script(script_name: str, args: List[str] = []):
    """Runs a Python script from src/ as a subprocess."""
    script_path = BASE_DIR / "src" / script_name
    cmd = [str(VENV_PYTHON), str(script_path)] + args
    
    # Run synchronously for simple steps (or await asyncio.create_subprocess_exec if preferred for non-blocking)
    # For simplicity of these short scripts, we'll use blocking for now, or asyncio wrapper.
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Script failed: {stderr.decode()}")
    
    return {"status": "success", "output": stdout.decode()}

# --- Endpoints ---

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
def update_config(update: ConfigUpdate):
    config = load_config()
    config["ladder"] = update.ladder
    config["penalty_ratio"] = update.penalty_ratio
    config["effort_threshold"] = update.effort_threshold
    config["time_limit_seconds"] = update.time_limit_seconds
    save_config(config)
    return {"status": "updated", "config": config}

@app.post("/api/run/download")
async def run_download():
    return await run_script("step_01_download_data.py")

@app.post("/api/run/aggregate")
async def run_aggregate():
    # Run step 2 and 3 together as "Aggregate" usually implies getting data ready
    await run_script("step_02_convert_data.py")
    return await run_script("step_03_aggregate_groups.py")

@app.post("/api/run/export")
async def run_export():
    return await run_script("step_05_export_csv.py")

@app.websocket("/api/solve/live")
async def websocket_solve(websocket: WebSocket):
    await websocket.accept()
    
    script_path = BASE_DIR / "src" / "step_04_run_solver.py"
    cmd = [str(VENV_PYTHON), "-u", str(script_path)] # -u for unbuffered stdout
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Read line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            line_str = line.decode().strip()
            
            # Simple parsing for visualization
            # Format: "Solution X, time = Y s, objective = Z, penalties = W"
            data = {"raw": line_str}
            
            if "objective =" in line_str:
                parts = line_str.split(',')
                try:
                    # Parse interesting bits
                    # "Solution 345" -> 345
                    # " time = 50.61 s" -> 50.61
                    # " objective = 2714.0" -> 2714.0
                    # " penalties = 148" -> 148
                    
                    obj_part = [p for p in parts if "objective =" in p][0]
                    time_part = [p for p in parts if "time =" in p][0]
                    pen_part = [p for p in parts if "penalties =" in p]
                    
                    objective = float(obj_part.split('=')[1].strip())
                    time_val = float(time_part.split('=')[1].strip().replace('s',''))
                    penalties = 0
                    if pen_part:
                        penalties = int(pen_part[0].split('=')[1].strip())

                    data["parsed"] = {
                        "time": time_val,
                        "objective": objective,
                        "penalties": penalties
                    }
                except Exception as e:
                    # ignore parsing errors for non-standard lines
                    pass

            await websocket.send_json(data)

        # Check for errors
        stderr_output = await process.stderr.read()
        if stderr_output:
            await websocket.send_json({"error": stderr_output.decode()})
            
        await process.wait()
        await websocket.send_json({"status": "complete", "return_code": process.returncode})
        
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
