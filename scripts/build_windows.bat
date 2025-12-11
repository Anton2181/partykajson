@echo off
setlocal
cd /d "%~dp0"
cd ..

echo ==========================================
echo    Building PartykaSolverPro for Windows
echo ==========================================

REM 1. Check for Virtual Environment (Windows Structure)
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Windows virtual environment not found!
    echo Checked path: .venv\Scripts\activate.bat
    echo.
    echo If you copied this project from Mac/Linux, delete the '.venv' folder
    echo and run the setup script or Create a new venv manually:
    echo py -m venv .venv
    echo.
    pause
    exit /b 1
)

REM 2. Activate Venv
echo [1/3] Activating Virtual Environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate .venv.
    pause
    exit /b 1
)

REM 3. Install Requirements
echo [2/3] Checking dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Failed to install requirements.
    echo Ensure you have internet access or pre-installed packages.
    pause
)

REM 4. Run Build Script
echo [3/3] Running Build...
python src\build.py
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo    BUILD SUCCESSFUL
echo ==========================================
echo Artifacts are in: dist\
echo You can reference 'dist\PartykaSolverPro\data' for config.
echo.
pause
