# PDF OCR & AUTO BOOKMARK PRO - PowerShell Startup Script
$ErrorActionPreference = "Stop"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "          PDF OCR & AUTO BOOKMARK PRO - PowerShell" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

# 1. Virtual environment check
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    $sysPython = "C:\Program Files\Python310\python.exe"
    if (Test-Path $sysPython) {
        & $sysPython -m venv .venv
    } else {
        python -m venv .venv
    }
}

# 2. Check dependencies
Write-Host "[*] Verifying python packages..." -ForegroundColor Yellow
& $venvPython -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt --quiet

# 3. Check OCR tools
if (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe") {
    Write-Host "[✓] Tesseract OCR found." -ForegroundColor Green
} else {
    Write-Host "[!] Tesseract OCR not found in default path." -ForegroundColor Yellow
}

# 4. Start Server
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host " Server running at: http://localhost:8000" -ForegroundColor Green
Write-Host " Press Ctrl+C in this terminal to stop the server." -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

Start-Process "http://localhost:8000"
& $venvPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
