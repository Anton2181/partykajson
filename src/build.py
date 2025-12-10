
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
        f"{data_path}{sep}data",       # Bundle entire data folder (config, members)
        f"{src_path}{sep}src",         # Bundle source code for subprocess execution
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
    print("Build Complete. Check 'dist' folder.")

if __name__ == "__main__":
    clean_build()
    build_app()
