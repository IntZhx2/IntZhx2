$Host.UI.RawUI.WindowTitle = "DeskMate Launcher"

$baseDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $baseDir "backend"))) {
    if (Test-Path (Join-Path $baseDir "deskmate\backend")) {
        $baseDir = Join-Path $baseDir "deskmate"
    }
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  DeskMate - One-Click All-in-One Service Launcher" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Start Backend (FastAPI on port 8000)
Write-Host "[1/3] Starting Backend (FastAPI on 127.0.0.1:8000)..." -ForegroundColor Yellow
$backendDir = Join-Path $baseDir "backend"
Start-Process cmd -ArgumentList @('/k', 'title DeskMate-Backend (Port 8000) & python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload') -WorkingDirectory $backendDir

Start-Sleep -Seconds 2

# 2. Start Frontend (Vite on port 5173)
Write-Host "[2/3] Starting Frontend (Vite on 127.0.0.1:5173)..." -ForegroundColor Yellow
$frontendDir = Join-Path $baseDir "frontend"
$hasPnpm = Get-Command pnpm -ErrorAction SilentlyContinue
if ($hasPnpm) {
    Start-Process cmd -ArgumentList @('/k', 'title DeskMate-Frontend (Port 5173) & pnpm dev') -WorkingDirectory $frontendDir
} else {
    Start-Process cmd -ArgumentList @('/k', 'title DeskMate-Frontend (Port 5173) & npm run dev') -WorkingDirectory $frontendDir
}

Start-Sleep -Seconds 1

# 3. Start Edge Agent (Hardware & Windows Agent)
Write-Host "[3/3] Starting Edge Agent (Hardware & Windows OS Agent)..." -ForegroundColor Yellow
$edgeDir = Join-Path $baseDir "edge"
Start-Process cmd -ArgumentList @('/k', 'title DeskMate-Edge (Hardware & System Agent) & python -m deskmate_edge') -WorkingDirectory $edgeDir

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  All services started successfully in separate windows!" -ForegroundColor Green
Write-Host "  Opening web console: http://127.0.0.1:5173 ..." -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:5173"

Write-Host "Tips:" -ForegroundColor Gray
Write-Host "1. Backend, Frontend, and Edge run in separate windows for easy monitoring." -ForegroundColor Gray
Write-Host "2. Type Q and press Enter here anytime to stop all services." -ForegroundColor Gray
Write-Host ""

while ($true) {
    $inputVal = Read-Host "Type Q to stop all services"
    if ($inputVal -match "^[qQ]$") {
        Write-Host "Stopping all DeskMate services..." -ForegroundColor Red
        $stopScript = Join-Path $baseDir "stop_deskmate.ps1"
        if (Test-Path $stopScript) {
            & $stopScript
        } else {
            & (Join-Path $PSScriptRoot "stop_deskmate.ps1")
        }
        break
    }
}
