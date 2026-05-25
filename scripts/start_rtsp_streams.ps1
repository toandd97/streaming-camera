param(
    [string]$VideoFile = "videos/sample.mp4",
    [int]$NumStreams = 4,
    [string]$RtspHost = "localhost",
    [string]$RtspPort = "8554"
)

if (-not (Test-Path $VideoFile)) {
    Write-Host "[ERROR] Video file not found: $VideoFile" -ForegroundColor Red
    exit 1
}

# Check if ffmpeg is installed
if (-not (Get-Command "ffmpeg" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] ffmpeg is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install ffmpeg (e.g. winget install ffmpeg) first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting $NumStreams RTSP streams from: $VideoFile" -ForegroundColor Cyan
Write-Host "RTSP server: rtsp://$RtspHost:$RtspPort" -ForegroundColor Cyan

$pidFile = "$env:TEMP\orbro_ffmpeg_pids.txt"
if (Test-Path $pidFile) { Remove-Item $pidFile }

for ($i = 1; $i -le $NumStreams; $i++) {
    $rtspUrl = "rtsp://$RtspHost:$RtspPort/cam$i"
    
    $args = @("-re", "-stream_loop", "-1", "-i", $VideoFile, "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-b:v", "500k", "-an", "-f", "rtsp", $rtspUrl, "-loglevel", "warning")
    
    $process = Start-Process -FilePath "ffmpeg" -ArgumentList $args -PassThru -WindowStyle Hidden
    
    $process.Id | Out-File -FilePath $pidFile -Append
    Write-Host "  [✓] Started cam$i -> $rtspUrl (PID: $($process.Id))" -ForegroundColor Green
}

Write-Host "`nAll $NumStreams streams started. PIDs saved to $pidFile" -ForegroundColor Cyan
Write-Host "To stop streams, run: .\scripts\stop_rtsp_streams.ps1" -ForegroundColor Yellow
