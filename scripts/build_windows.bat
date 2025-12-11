@echo off
setlocal
cd /d "%~dp0"
cd ..

echo ==========================================
echo    Building PartykaSolverPro for Windows
echo ==========================================

REM 1. Check for Virtual Environment
if not exist .venv (
    echo [ERROR] Virtual environment '.venv' not found!
    echo Please run setup first (or create .venv manually).
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

REM 3. Install Requirements (Optional but good safety)
echo [2/3] Checking dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Failed to install requirements. Trying to proceed...
)

REM 4. Run Build Script
echo [3/3] Running Build...
python src\build.py
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo ==========================================
echo    BUILD SUCCESSFUL
echo ==========================================
echo Artifacts are in: dist\
echo You can reference 'dist\PartykaSolverPro\data' for config.
pause
