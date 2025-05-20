#!/usr/bin/env pwsh

# Setup script for Jarvis MVP API
Write-Host "Setting up Jarvis MVP API..." -ForegroundColor Green

# Check if Python is installed
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python is not installed. Please install Python 3.8 or higher and try again." -ForegroundColor Red
    exit 1
}
Write-Host "Python version: $pythonVersion" -ForegroundColor Green

# Create and activate virtual environment
Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists. Skipping creation." -ForegroundColor Yellow
} else {
    python -m venv venv
}

# Activate virtual environment
$activateScript = ".\venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
    Write-Host "Virtual environment activated." -ForegroundColor Green
} else {
    Write-Host "Failed to activate virtual environment. Script not found: $activateScript" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Set up environment variables
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "`nCreating .env file from example..." -ForegroundColor Yellow
    Copy-Item ".env.example" $envFile
    Write-Host "Please edit the .env file with your configuration." -ForegroundColor Yellow
} else {
    Write-Host ".env file already exists. Skipping creation." -ForegroundColor Yellow
}

# Initialize database (if needed)
# python -m src.cli initdb --yes

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "To start the API server, run: .\start_api.ps1" -ForegroundColor Cyan
Write-Host "To test the API, run: .\test_api.ps1" -ForegroundColor Cyan
