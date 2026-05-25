Write-Host "=== ORBRO B1: Camera Monitoring System Setup ===" -ForegroundColor Cyan

# 1. Environment file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created .env file" -ForegroundColor Green
}

# 2. Check for video
$videoFile = $null
if (Test-Path "video") {
    $videos = Get-ChildItem -Path "video" -Filter "*.mp4"
    if ($videos.Count -gt 0) {
        $videoFile = "video/" + $videos[0].Name
        Write-Host "[OK] Using existing video: $videoFile" -ForegroundColor Green
    }
}
if ($null -eq $videoFile) {
    if (Test-Path "videos\sample.mp4") {
        $videoFile = "videos/sample.mp4"
        Write-Host "[OK] Using existing video: $videoFile" -ForegroundColor Green
    } else {
        New-Item -ItemType Directory -Force -Path "videos" | Out-Null
        Write-Host "[INFO] Downloading sample video (Big Buck Bunny ~1MB)..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4" -OutFile "videos\sample.mp4"
        $videoFile = "videos/sample.mp4"
        Write-Host "[OK] Downloaded sample video." -ForegroundColor Green
    }
}

# 3. Docker Compose
Write-Host "[INFO] Starting Docker containers..." -ForegroundColor Yellow
docker compose down
docker compose up -d --build
Write-Host "[OK] Docker containers started." -ForegroundColor Green

Start-Sleep -Seconds 3

# 4. Wait for backend to be ready
Write-Host "[INFO] Waiting for backend to be ready..." -ForegroundColor Yellow
$maxRetries = 30
$retry = 0
while ($retry -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/system/metrics" -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] Backend is ready!" -ForegroundColor Green
            break
        }
    } catch {
        # ignore error, wait and retry
    }
    Start-Sleep -Seconds 2
    $retry++
}

# 5. Start RTSP streams
Write-Host "[INFO] Starting 4 RTSP simulation streams..." -ForegroundColor Yellow
& .\scripts\start_rtsp_streams.ps1 -VideoFile $videoFile -NumStreams 4
Start-Sleep -Seconds 3

# 6. Register cameras
Write-Host "[INFO] Registering demo cameras..." -ForegroundColor Yellow
& .\scripts\register_demo_cameras.ps1

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "Open Dashboard: http://localhost:8000" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
