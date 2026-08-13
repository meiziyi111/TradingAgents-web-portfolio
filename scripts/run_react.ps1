$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$distIndex = Join-Path $frontendRoot "dist\index.html"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Project virtual environment not found: $pythonPath"
}

if (-not (Test-Path -LiteralPath $distIndex)) {
    Write-Host "React production build not found; building it now..."
    Push-Location $frontendRoot
    try {
        npm.cmd install
        npm.cmd run build
    }
    finally {
        Pop-Location
    }
}

Push-Location $projectRoot
try {
    Write-Host "TradingAgents React is available at http://127.0.0.1:8000"
    & $pythonPath -m uvicorn tradingagents.web.api:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
