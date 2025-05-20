#!/usr/bin/env pwsh

# Start the FastAPI application with Uvicorn
Write-Host "Starting Jarvis MVP API..." -ForegroundColor Green
$env:PYTHONPATH = "."
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

# To run in production (without auto-reload):
# uvicorn src.api:app --host 0.0.0.0 --port 8000 --workers 4
