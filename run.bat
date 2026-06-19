@echo off
setlocal

echo.
echo  === Physics Quiz System - Starting ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [Step 0/3] Cleaning stale cache...
for /d /r "%~dp0" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

if not exist "%~dp0venv" (
    echo [Step 1/3] Creating virtual environment...
    python -m venv "%~dp0venv"
)

echo [Step 2/3] Installing dependencies...
call "%~dp0venv\Scripts\activate.bat"
pip install --quiet -r "%~dp0requirements.txt"

echo.
echo [Step 3/3] Launching Streamlit...
start "" "http://localhost:8501"
streamlit run "%~dp0app.py" --server.headless true --browser.gatherUsageStats false

endlocal
