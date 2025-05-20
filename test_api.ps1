#!/usr/bin/env pwsh

# Test the API endpoints
Write-Host "Testing Jarvis MVP API..." -ForegroundColor Cyan

# Test health check
Write-Host "`n[TEST] Health Check..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -Method Get
Write-Host "Status: $($response.status)"

# Test getting orders
Write-Host "`n[TEST] Get Orders..." -ForegroundColor Yellow
$orders = Invoke-RestMethod -Uri "http://localhost:8000/orders?limit=2" -Method Get
$orders | ConvertTo-Json -Depth 3 | Write-Host

# Test generating a reply
Write-Host "`n[TEST] Generate Reply..." -ForegroundColor Yellow
$body = @{
    id = "test123"
    title = "Need a Python developer for web scraping"
    source = "local"
    send = $false
} | ConvertTo-Json

try {
    $reply = Invoke-RestMethod -Uri "http://localhost:8000/generate-reply" -Method Post -Body $body -ContentType "application/json"
    $reply | ConvertTo-Json -Depth 3 | Write-Host
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Response: $($_.Exception.Response.StatusCode.value__) - $($_.Exception.Response.StatusDescription)"
}

Write-Host "`nAPI Tests Complete!" -ForegroundColor Green
