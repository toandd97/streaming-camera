# Architecture Documentation

## System Architecture

```text
resources/videos/*.mp4 -> cached low-bandwidth rendition (prepared once)
    -> demo-publisher (one FFmpeg loop per source, H.264 stream-copy)
    -> MediaMTX
         |-- RTSP input paths: /demo/garden, /demo/office, ...
         |-- HLS output :8888 -> Browser / hls.js
         `-- API :9997 -> FastAPI StreamManager poller

FastAPI :8000
    |-- Camera CRUD API -> MongoDB
    |-- StreamManager -> one periodic MediaMTX API query for all cameras
    |-- MetricsService / AlertService / WebSocket updates
    `-- Static dashboard -> visible tiles load HLS lazily
```

## Data Flow

### Demo Input

`demo-publisher` publishes every H.264 `.mp4` in `resources/videos/` on a stable RTSP path:

```text
resources/videos/garden.mp4 -> rtsp://mediamtx:8554/demo/garden
resources/videos/office.mp4 -> rtsp://mediamtx:8554/demo/office
```

On first startup it creates cached 640x360, 10 FPS, low-bitrate H.264
renditions. Continuous publication then uses FFmpeg stream-copy (`-c:v copy`)
rather than keeping an encoder per channel. Camera CRUD remains independent:
an added camera stores one of these RTSP URLs, or any external RTSP URL.

### Browser Playback

```text
MediaMTX RTSP path -> MediaMTX HLS muxer -> /<path>/index.m3u8 -> hls.js video
```

FastAPI is not on the video data path. The frontend only opens HLS playback for
visible camera tiles, avoiding dozens of concurrent players on a dashboard page.

### Status And Reconnect

```text
StreamManager -> GET MediaMTX /v3/paths/list every 5 seconds
    ready source exists -> CONNECTED, update uptime
    source disappears -> DISCONNECTED -> RECONNECTING, emit event
    source returns -> CONNECTED, emit event
```

This detects a stopped publisher or broken RTSP source. It does not yet inspect
decoded frames or calculate actual FPS/latency; those fields should not be used
as measurement results until a frame/telemetry probe is added.

## Scale Considerations

- Backend work is one MediaMTX status poll plus metadata APIs, not one OpenCV
  decoder per camera.
- Demo publishers continuously stream-copy cached low-bitrate inputs; one-time
  cache preparation avoids the original files' excessive bandwidth.
- MediaMTX performs HLS packaging; browser load is limited through lazy tile
  playback.
- The requirement targets 32 channels. Operation at 80 channels is an analysis
  and benchmark scenario, not a claim without measurements on the deployment
  hardware.
- Bottlenecks to measure are publisher and HLS I/O, MediaMTX memory, aggregate
  bandwidth, and the number of simultaneously visible browser players.

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `scripts/publish_demo_library.sh` | Reproducible distinct RTSP demo sources |
| `mediamtx.yml` | RTSP reception, HLS delivery, status API |
| `services/stream_manager.py` | Runtime state derived from MediaMTX paths |
| `services/camera_service.py` | Camera CRUD and runtime merge |
| `web/app.js` | HLS playback, lazy tile loading, register/edit UI |
| `metrics_service.py` | CPU/RAM/GPU host metrics |
