
import os
import shutil
import platform
import subprocess
from pathlib import Path
import PyInstaller.__main__

import time

def clean_build():
    """Remove previous build artifacts with retry logic for Windows locks."""
    directories = ["build", "dist"]
    
    for d in directories:
        if os.path.exists(d):
            print(f"Cleaning {d}...")
            # Try up to 5 times
            for attempt in range(5):
                try:
                    shutil.rmtree(d)
                    break # Success
                except OSError:
                    if attempt < 4:
                        print(f"  [Attempt {attempt+1}] File locked or directory busy. Retrying in 1s...")
                        time.sleep(1)
                    else:
                        print(f"  [ERROR] Could not delete '{d}'. Please close any open folders or running instances of the app.")
                        raise
                except Exception as e:
                    print(f"  [ERROR] Deleting '{d}' failed: {e}")
                    raise
    
    spec_file = "PartykaSolverPro.spec"
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
        except OSError:
            pass

def build_app():
    """Run PyInstaller."""
    base_dir = Path(__file__).parent.parent
    src_dir = base_dir / "src"
    
    # Define Entry Point
    script = str(src_dir / "gui.py")
    
    # Define Name
    app_name = "Partyka Assigner Script"
    
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
        # Bundle defaults for fallback (User Docs mode)
        f"{data_path}{sep}data_defaults"
    ]
    
    # Hidden Imports (OR-Tools, Pandas often need help)
    hidden_imports = [
        "pandas",
        "matplotlib",
        "matplotlib.backends.backend_svg",
        "pyqtgraph",
        "PyQt6.QtSvgWidgets",
        "PyQt6.QtSvg",
        "src.default_families",
        "src.default_team",
        "src.rule_descriptions"
    ]
    
    # Collect OR-Tools dependencies automatically (fixes DLL load errors)
    from PyInstaller.utils.hooks import collect_all
    tmp_ret = collect_all('ortools')
    
    # Add collected data to our lists
    # datas, binaries, hiddenimports
    for d in tmp_ret[0]:
        add_data.append(f"{d[0]}{sep}{d[1]}")
        
    for h in tmp_ret[2]:
        hidden_imports.append(h)
        
    # Binaries need to be passed effectively, but PyInstaller command line args 
    # for binaries are --add-binary. Let's collect them.
    add_binaries = []
    for b in tmp_ret[1]:
        add_binaries.append(f"{b[0]}{sep}{b[1]}")

    dist_dir = base_dir / "dist"
    build_dir = base_dir / "build"
    icon_path = base_dir / "PartykaIcon.png"
    
    args = [
        script,
        f"--name={app_name}",
        "--windowed",            # No console window
        "--noconfirm",           # Overwrite output directory
        "--clean",               # Clean cache
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
    ]
    
    # Add Icon if exists
    if icon_path.exists():
        args.append(f"--icon={icon_path}")
    
    # Add Data
    for d in add_data:
        args.append(f"--add-data={d}")
        
    # Add Binaries
    for b in add_binaries:
        args.append(f"--add-binary={b}")
        
    # Add Hidden Imports
    for h in hidden_imports:
        args.append(f"--hidden-import={h}")
        
    # OS Specific
    if platform.system() == "Darwin":
        # Mac bundle identifier code signing identity could go here
        # For now simple app build
        pass
        
    print(f"Building {app_name}...")
    # Clean previous build artifacts again to be safe
    # Actually run process to handle arch switching if needed? 
    # Calling run() directly runs in-process. 
    # If python is universal, this *should* work.
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
    
    # Copy Static Config & Icon
    files_to_copy = ["penalty_config.json", "team_members.json", "task_families.json"]
    for f in files_to_copy:
        src = data_path / f
        dst = target_data_dir / f
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Copied {f} to {target_data_dir}")

    # Copy Icon to Data Directory (Organized)
    icon_src = base_dir / "PartykaIcon.png"
    if icon_src.exists():
        # Place it in target_data_dir (which is dist/data or dist/App/data)
        shutil.copy2(icon_src, target_data_dir / "PartykaIcon.png")
        print(f"Copied icon to {target_data_dir}")
            
    print("Build Complete. Check 'dist' folder.")

if __name__ == "__main__":
    clean_build()
    build_app()
