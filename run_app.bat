@echo off
setlocal enabledelayedexpansion
title PDF OCR ^& AUTO BOOKMARK PRO - Launcher

echo ================================================================
echo           PDF OCR ^& AUTO BOOKMARK PRO - Local Launcher
echo ================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python installation
echo [*] Checking Python environment...
set PYTHON_CMD=

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=py -3.10
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set PYTHON_CMD=python
    ) else (
        if exist "C:\Program Files\Python310\python.exe" (
            set PYTHON_CMD="C:\Program Files\Python310\python.exe"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.10 or 3.11 from https://www.python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: 2. Check / Create Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (.venv)...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

:: 3. Check and install dependencies
echo [*] Verifying dependencies...
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt --quiet

:: 4. Check OCR prerequisites (Tesseract & Ghostscript)
echo [*] Checking Tesseract OCR and Ghostscript...
where tesseract >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo [WARNING] Tesseract OCR is not detected in standard location.
        echo If OCR fails, please install Tesseract from:
        echo https://github.com/UB-Mannheim/tesseract/wiki
    )
)

:: 5. Launch FastAPI application
echo.
echo ================================================================
echo  Application is starting on: http://localhost:8000
echo  Press Ctrl+C to stop the server at any time.
echo ================================================================
echo.

:: Open browser after 2 seconds in background
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000"

:: Run Uvicorn
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause
