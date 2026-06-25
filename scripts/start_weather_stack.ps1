# Start Open WebUI (:3000) + local Flask weather API (:5000).
# Run from repo root: .\scripts\start_weather_stack.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host "Starting Open WebUI on http://localhost:3000 ..."
$webui = docker ps -a --filter "name=^open-webui$" --format "{{.Names}}"
if (-not $webui) {
    Write-Host "open-webui container not found. Create it with:"
    Write-Host "  docker compose -f docker-compose.weather.yml up -d"
    exit 1
}
docker start open-webui | Out-Null

Write-Host "Starting weather API on http://localhost:5000 ..."
if (Test-PortListening 5000) {
    Write-Host "Port 5000 already in use; skipping Flask start."
} else {
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Write-Host "Missing venv at $python"
        exit 1
    }
    Start-Process -FilePath $python -ArgumentList (Join-Path $Root "app.py") -WorkingDirectory $Root -WindowStyle Minimized
    Start-Sleep -Seconds 2
}

foreach ($url in @("http://localhost:3000/", "http://localhost:5000/health")) {
    try {
        $code = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15).StatusCode
        Write-Host "OK $url HTTP $code"
    } catch {
        Write-Host "FAIL $url $($_.Exception.Message)"
        exit 1
    }
}

Write-Host ""
Write-Host "Ready:"
Write-Host "  Web UI:      http://localhost:3000"
Write-Host "  Weather API: http://localhost:5000/weather?city=Tel%20Aviv"
Write-Host ""
Write-Host "Register the tool in Open WebUI: Settings, Tools, plus button"
Write-Host "  Base URL: http://localhost:5000"
Write-Host "  OpenAPI path: openapi.json"
Write-Host ""
Write-Host "GetWeather filter: Admin, Functions, enable getweather on your model"
Write-Host "  Re-seed: .\.venv\Scripts\python.exe scripts\seed_openwebui_functions.py"
