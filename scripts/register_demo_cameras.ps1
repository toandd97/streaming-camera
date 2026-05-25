param(
    [string]$BaseUrl = "http://localhost:8000"
)

$apiUrl = "$BaseUrl/api/v1"
# When backend runs in Docker: use mediamtx hostname
$rtspHost = "mediamtx"

$cameras = @(
    @{ Name = "Cam 1 (Main Gate)"; Path = "cam1" },
    @{ Name = "Cam 2 (Parking)"; Path = "cam2" },
    @{ Name = "Cam 3 (Warehouse)"; Path = "cam3" },
    @{ Name = "Cam 4 (Office)"; Path = "cam4" }
)

Write-Host "Registering 4 demo cameras to $apiUrl" -ForegroundColor Cyan

foreach ($cam in $cameras) {
    $name = $cam.Name
    $path = $cam.Path
    $rtspUrl = "rtsp://$rtspHost:8554/$path"
    
    Write-Host "Registering: $name -> $rtspUrl"
    
    $body = @{
        name = $name
        rtsp_url = $rtspUrl
        resolution = "640x360"
        target_fps = 10
        display_fps = 5
        enabled = $true
        description = "Demo camera"
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "$apiUrl/cameras" -Method Post -Body $body -ContentType "application/json"
        Write-Host "  [✓] Created (ID: $($response.id))" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Failed: $_" -ForegroundColor Red
    }
}

Write-Host "`nDone! Refresh your dashboard." -ForegroundColor Cyan
