$pidFile = "$env:TEMP\orbro_ffmpeg_pids.txt"

if (Test-Path $pidFile) {
    Write-Host "Stopping FFmpeg processes (from PID file)..." -ForegroundColor Cyan
    $pids = Get-Content $pidFile
    foreach ($p in $pids) {
        try {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "  [✓] Stopped PID $p" -ForegroundColor Green
        } catch {
            Write-Host "  [!] Could not stop PID $p" -ForegroundColor Yellow
        }
    }
    Remove-Item $pidFile
} else {
    Write-Host "No PID file found. Trying to kill all ffmpeg processes..." -ForegroundColor Yellow
    Get-Process -Name ffmpeg -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "  [✓] Stopped all FFmpeg processes" -ForegroundColor Green
}

Write-Host "Done. Cameras will enter DISCONNECTED -> RECONNECTING state." -ForegroundColor Cyan
