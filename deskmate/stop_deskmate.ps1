Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "  Stopping all DeskMate services..." -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow

# 1. Close cmd windows with titles
Get-Process cmd -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -like "DeskMate-*"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Free ports 8000 and 5173
@(8000, 5173) | ForEach-Object {
    $port = $_
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            if ($p -gt 4) {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host "All DeskMate services stopped cleanly." -ForegroundColor Green
Start-Sleep -Seconds 1
