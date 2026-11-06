@echo off
setlocal
title PDF OCR & AUTO BOOKMARK PRO
cd /d "%~dp0"
echo ================================================================
echo          PDF OCR & AUTO BOOKMARK PRO
echo ================================================================
echo.
echo [1/4] Checking virtual environment...
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
)
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Could not create virtual environment.
    pause
    exit /b 1
)
echo [2/4] Activating environment...
call ".venv\Scripts\activate.bat"
echo [3/4] Checking dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)
echo [4/4] Starting application...
echo.
echo Website: http://127.0.0.1:8000
echo Press CTRL+C to stop.
echo.
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
