# WearForge Runner Script (Windows / PowerShell)
# Mirrors run.sh: creates a venv, installs dependencies, and launches the app.
#
# Usage:  .\run.ps1 [options]   e.g.  .\run.ps1 --device 192.168.1.42:5555

$ErrorActionPreference = "Stop"

Write-Host "=== WearForge CLI Bootstrap ===" -ForegroundColor Blue

# Check for Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Host "Error: Python 3 is required but was not found on PATH." -ForegroundColor Red
    exit 1
}

# Check for ADB
if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: 'adb' was not found on PATH." -ForegroundColor Yellow
    Write-Host "Install Android platform-tools (e.g. 'winget install Google.PlatformTools')." -ForegroundColor Yellow
    Write-Host ""
}

# Work from the script's directory
Set-Location -Path $PSScriptRoot

# Create the venv if missing
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment in .venv..."
    & $python.Source -m venv .venv
}

# Use the venv's Python directly (no activation needed)
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "Checking/installing dependencies..."
& $venvPython -m pip install -q --upgrade pip
& $venvPython -m pip install -q -r requirements.txt

Write-Host "Dependencies OK. Starting WearForge..." -ForegroundColor Green
Write-Host ""
& $venvPython wearforge.py @args
