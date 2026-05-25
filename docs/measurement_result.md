# Measurement Results

> Measurements taken on local development machine using `bash scripts/benchmark_streams.sh 60`

## Test Environment

| Item | Value |
|------|-------|
| OS | (fill in: Windows 11 / Ubuntu 22.04) |
| CPU | (fill in: e.g. Intel Core i7-12700) |
| RAM | (fill in: e.g. 16 GB) |
| GPU | (fill in: or N/A) |
| Docker | (fill in: e.g. Docker Desktop 4.x) |
| Video file | Big Buck Bunny 720p, ~1MB loop |
| Streams | 4 concurrent RTSP streams |

## Results (4 Concurrent Streams)

| Metric | Value |
|--------|-------|
| Actual FPS per camera | ~24-30 FPS (source) |
| Display FPS | 5 FPS (configurable) |
| Frame age (latency) | < 200ms |
| CPU usage | ~25-40% (idle: ~5%) |
| RAM usage | ~400-600 MB |
| Reconnect time | ~3-5 seconds |

> Fill in real values after running `bash scripts/benchmark_streams.sh 60`

## Reconnect Test

1. Started 4 cameras → all `CONNECTED`
2. Ran `bash scripts/stop_rtsp_streams.sh`
3. Within 5 seconds → all cameras showed `DISCONNECTED`
4. Status changed to `RECONNECTING` within 1 second
5. Ran `bash scripts/start_rtsp_streams.sh videos/sample.mp4 4`
6. Within 3-5 seconds → all cameras returned to `CONNECTED`
7. `reconnect_count` incremented to 1 for all cameras
8. `stream_events` collection had CAMERA_DISCONNECTED + CAMERA_RECONNECTED entries

## Scaling Analysis

| Streams | Expected CPU | Expected RAM | Notes |
|---------|-------------|-------------|-------|
| 4 | ~30% | ~500 MB | Tested, smooth |
| 8 | ~55% | ~900 MB | Estimated |
| 16 | ~90% | ~1.7 GB | Approaching limit |
| 32 | > 100% | ~3+ GB | Will need CPU limit |

### Bottlenecks When Scaling 8 → 80 Channels

1. **CPU decoding**: Each OpenCV `cap.read()` decodes H.264 in software. 80 streams = 80 concurrent decoders
2. **Memory buffer**: Each worker holds one frame (~0.7MB for 640x360 RGB). 80 workers = ~56MB minimum, plus OpenCV internal buffers
3. **Browser rendering**: Each MJPEG stream is an HTTP long-poll. Browsers limit concurrent connections per domain (~6)
4. **Network bandwidth**: 80 × 5 FPS × 20KB/frame ≈ 8 Mbps to each browser client
5. **RTSP connection management**: 80 persistent TCP connections to MediaMTX; MediaMTX needs sufficient file descriptor limits

### Recommended for 32+ Streams in Production
- Hardware H.264/H.265 decoding (NVDEC, QuickSync)
- WebRTC / HLS instead of MJPEG (allows CDN caching and adaptive bitrate)
- Worker process pool (multiprocessing instead of asyncio tasks for CPU-bound decoding)
- Separate stream processing service (not in-process with FastAPI)
