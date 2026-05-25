# ORBRO B1 — Camera Management & Streaming Video System

> **ORBRO Vina Backend Developer Test — B1**
> Stack: FastAPI + MongoDB + MediaMTX + FFmpeg + OpenCV + MJPEG Web UI

## Quick Start (One Command)

```bash
git clone <repo-url> camera-monitoring
cd camera-monitoring
bash setup.sh
```

Open: **http://localhost:8000** 🎉

---

## Project Overview

A real-time camera monitoring backend that:
- Simulates multiple RTSP cameras from a video file (FFmpeg + MediaMTX)
- Manages camera configurations via REST API (`/api/v1`)
- Reads RTSP streams per camera using OpenCV (one `StreamWorker` per camera)
- Serves live video to browsers via MJPEG (`<img>` tag)
- Detects stream failures and auto-reconnects
- Displays FPS, latency, uptime, reconnect count on a dark-mode web dashboard
- Stores camera config and stream events in MongoDB
- Optional: Telegram alerts on failure

---

## Architecture

```
Video file (sample.mp4)
    → FFmpeg (loop) → MediaMTX (RTSP server :8554)
                          ↓
          FastAPI Backend (:8000)
            ├── Camera Registry API → MongoDB (cameras collection)
            ├── StreamManager
            │     └── StreamWorker × N
            │           ├── OpenCV reads RTSP frames
            │           ├── Calculates FPS, latency, frame_age
            │           ├── Detects timeout → DISCONNECTED
            │           └── Auto-reconnects → RECONNECTING → CONNECTED
            ├── MJPEG Endpoint → <img> in browser
            ├── MetricsService → CPU/RAM/GPU via psutil/pynvml
            ├── AlertService → stream_events (MongoDB) + Telegram (optional)
            ├── WebSocketManager → real-time push to dashboard
            └── Static Web UI (index.html / app.js / styles.css)
```

**Core Principle:**
- MongoDB = persistent data (camera config, events)
- Memory = runtime data (frame buffer, FPS, status) — never written every frame

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | MongoDB 7, Motor (async) |
| RTSP Simulation | MediaMTX, FFmpeg |
| Stream Reading | OpenCV (cv2) |
| System Metrics | psutil, pynvml (optional GPU) |
| Alerts | MongoDB storage + Telegram Bot API (optional) |
| Web UI | Vanilla HTML/CSS/JS (no framework) |
| Deployment | Docker, Docker Compose |

---

## Folder Structure

```
orbro/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── core/                # config, logging, constants
│   ├── api/
│   │   └── v1/              # versioned routes (camera, stream, metrics, events, ws)
│   ├── db/                  # MongoDB connection + indexes
│   ├── models/              # DB documents + RuntimeStatus dataclass
│   ├── schemas/             # Pydantic request/response schemas
│   ├── repositories/        # Direct MongoDB access layer
│   ├── services/            # Business logic (StreamWorker, StreamManager, ...)
│   ├── utils/               # FPS calculator, time utils, image utils
│   └── web/                 # Dashboard: index.html, styles.css, app.js
├── scripts/
│   ├── start_rtsp_streams.sh
│   ├── stop_rtsp_streams.sh
│   ├── register_demo_cameras.sh
│   └── benchmark_streams.sh
├── videos/                  # Place sample.mp4 here
├── tests/                   # pytest unit tests
├── docs/                    # Architecture, API examples, measurements
├── setup.sh                 # One-command setup
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```env
MONGO_URI=mongodb://mongo:27017
MONGO_DB_NAME=camera_monitoring

NO_FRAME_TIMEOUT_SECONDS=5       # Seconds before DISCONNECTED
RECONNECT_INTERVAL_SECONDS=3     # Seconds between reconnect attempts

CPU_ALERT_THRESHOLD=90           # % CPU before HIGH_CPU alert
MEMORY_ALERT_THRESHOLD=85        # % RAM before HIGH_MEMORY alert
ALERT_COOLDOWN_SECONDS=60        # Minimum time between same alerts

TELEGRAM_ENABLED=false           # Set true + add token/chat_id for alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

MJPEG_JPEG_QUALITY=80            # 1-100
```

---

## How to Run

### With Docker Compose (recommended)

```bash
# Full automated setup:
bash setup.sh

# Or manually:
cp .env.example .env
docker compose up -d --build
bash scripts/start_rtsp_streams.sh videos/sample.mp4 4
bash scripts/register_demo_cameras.sh
```

### Without Docker (development)

```bash
pip install -r requirements.txt
# Start MongoDB and MediaMTX separately, then:
uvicorn app.main:app --reload --port 8000
```

---

## How to Start RTSP Demo Streams

```bash
# Start 4 RTSP streams from sample video
bash scripts/start_rtsp_streams.sh videos/sample.mp4 4

# Streams available at:
# rtsp://localhost:8554/cam1
# rtsp://localhost:8554/cam2
# rtsp://localhost:8554/cam3
# rtsp://localhost:8554/cam4
```

---

## How to Register 4 Cameras

```bash
bash scripts/register_demo_cameras.sh

# Or manually via curl:
curl -X POST http://localhost:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{"name":"Camera 1","rtsp_url":"rtsp://mediamtx:8554/cam1","enabled":true}'
```

---

## How to Open Web Dashboard

Navigate to **http://localhost:8000**

- See 4 live MJPEG streams in a 2×2 grid
- Monitor FPS, latency, uptime, reconnect count per camera
- View CPU/RAM/GPU in the header
- Real-time event log via WebSocket

API Docs: **http://localhost:8000/docs**

---

## How to Change Display FPS

**Via UI:** Use the FPS dropdown on each camera tile (1, 3, 5, 10, 15).

**Via API:**
```bash
curl -X PATCH http://localhost:8000/api/v1/cameras/{camera_id}/display-fps \
  -H "Content-Type: application/json" \
  -d '{"display_fps": 10}'
```
Applied immediately — no RTSP reconnect needed.

---

## How to Test Stream Disconnection and Auto-Reconnect

```bash
# 1. Stop all RTSP streams:
bash scripts/stop_rtsp_streams.sh

# 2. Observe dashboard: tiles turn DISCONNECTED → RECONNECTING

# 3. Restart streams:
bash scripts/start_rtsp_streams.sh videos/sample.mp4 4

# 4. Observe dashboard: tiles return to CONNECTED
# 5. Check reconnect_count increased on each tile
```

---

## How to Check MongoDB Data

```bash
docker exec -it orbro_mongo mongosh camera_monitoring

# List cameras:
db.cameras.find().pretty()

# List recent events:
db.stream_events.find().sort({created_at:-1}).limit(10).pretty()
```

---

## How to Enable Telegram (Optional)

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. Get your `chat_id`
3. Update `.env`:
```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```
4. Restart backend: `docker compose restart backend`

Telegram alerts fire on: `CAMERA_DISCONNECTED`, `CAMERA_RECONNECTED`, `HIGH_CPU`, `HIGH_MEMORY`
with a 60-second cooldown per event type per camera.

---

## How to Run Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with asyncio mode
pytest tests/ -v --asyncio-mode=auto
```

---

## How to Reproduce Measurements

```bash
# Start system and streams
bash setup.sh

# Monitor for 60 seconds
bash scripts/benchmark_streams.sh 60

# Output: timestamp, CPU%, RAM%, active streams, FPS per camera
```

See `docs/measurement_result.md` for recorded results.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/cameras` | Register camera + start stream |
| GET | `/api/v1/cameras` | List all cameras with runtime status |
| GET | `/api/v1/cameras/{id}` | Get one camera |
| PUT | `/api/v1/cameras/{id}` | Update camera config |
| DELETE | `/api/v1/cameras/{id}` | Stop and delete camera |
| GET | `/api/v1/cameras/{id}/status` | Runtime status only |
| PATCH | `/api/v1/cameras/{id}/display-fps` | Hot-update display FPS |
| GET | `/api/v1/streams/{id}/mjpeg` | MJPEG video stream |
| GET | `/api/v1/system/metrics` | CPU/RAM/GPU metrics |
| GET | `/api/v1/stream-events` | Stream event log |
| WS | `/api/v1/ws/dashboard` | Real-time dashboard push |

Full interactive docs: http://localhost:8000/docs

---

## Known Limitations

- **MJPEG** is simpler than WebRTC/HLS but uses more bandwidth per client
- **Single machine**: designed for demo with 4 streams; 32+ streams require a more powerful host
- **No authentication**: API is open; add JWT for production
- **Windows**: scripts are `.sh`; use WSL or Git Bash on Windows
- **GPU metrics**: only NVIDIA GPUs via `pynvml`

---

## Production Improvements

- Replace MJPEG with **WebRTC** or **HLS** for scalable video delivery
- Add **Prometheus + Grafana** for metrics observability
- Use **Redis** for shared runtime state across multiple backend instances
- Add **JWT authentication** and role-based access control
- Centralized logging with **Loki** or **ELK**
- Use **Alertmanager/PagerDuty** instead of Telegram for production alerts
- Horizontal scaling with **Kubernetes**
