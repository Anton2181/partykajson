
import os
import shutil
import platform
import subprocess
from pathlib import Path
import PyInstaller.__main__

def clean_build():
    """Remove previous build artifacts."""
    for d in ["build", "dist"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    
    spec_file = "PartykaSolverPro.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

def build_app():
    """Run PyInstaller."""
    base_dir = Path(__file__).parent.parent
    src_dir = base_dir / "src"
    
    # Define Entry Point
    script = str(src_dir / "gui.py")
    
    # Define Name
    app_name = "PartykaSolverPro"
    
    # Separator for data files (Windows uses ;, Unix uses :)
    sep = ';' if platform.system() == "Windows" else ':'
    
    # Data Files to Include
    # Format: "source_path{sep}dest_path"
    # Use absolute paths for source to avoid CWD issues
    data_path = base_dir / "data"
    src_path = base_dir / "src"
    
    add_data = [
        # Only bundle source code. Data is external.
        f"{src_path}{sep}src",         
    ]
    
    # Hidden Imports (OR-Tools, Pandas often need help)
    hidden_imports = [
        "ortools",
        "ortools.sat",
        "ortools.sat.python",
        "ortools.sat.python.cp_model",
        "pandas",
        "pyqtgraph",
        "PyQt6.QtSvgWidgets",
        "PyQt6.QtSvg"
    ]
    
    args = [
        script,
        f"--name={app_name}",
        "--windowed",            # No console window
        "--noconfirm",           # Overwrite output directory
        "--clean",               # Clean cache
    ]
    
    # Add Data
    for d in add_data:
        args.append(f"--add-data={d}")
        
    # Add Hidden Imports
    for h in hidden_imports:
        args.append(f"--hidden-import={h}")
        
    # OS Specific
    if platform.system() == "Darwin":
        # Mac bundle identifier code signing identity could go here
        # For now simple app build
        pass
        
    print(f"Building {app_name}...")
    PyInstaller.__main__.run(args)
    
    # --- Post-Build: Copy External Data ---
    print("Post-processing data files...")
    dist_dir = base_dir / "dist"
    
    # Target Data Directory
    if platform.system() == "Windows":
        target_data_dir = dist_dir / app_name / "data"
    else:
        # Mac - put data next to .app
        target_data_dir = dist_dir / "data"
        
    target_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy Static Config
    files_to_copy = ["penalty_config.json", "team_members.json", "task_families.json"]
    for f in files_to_copy:
        src = data_path / f
        dst = target_data_dir / f
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Copied {f} to {target_data_dir}")
            
    print("Build Complete. Check 'dist' folder.")

if __name__ == "__main__":
    clean_build()
    build_app()
