# Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORBRO B1 System                          │
│                                                                 │
│  ┌──────────┐    ┌─────────────┐    ┌────────────────────────┐ │
│  │ sample   │───▶│   FFmpeg    │───▶│     MediaMTX           │ │
│  │ .mp4     │    │ (loop x N)  │    │  RTSP Server :8554     │ │
│  └──────────┘    └─────────────┘    └────────────┬───────────┘ │
│                                                  │ rtsp://     │
│  ┌───────────────────────────────────────────────▼───────────┐ │
│  │                   FastAPI Backend :8000                   │ │
│  │                                                           │ │
│  │  ┌─────────────┐   ┌──────────────────────────────────┐  │ │
│  │  │  REST API   │   │          StreamManager           │  │ │
│  │  │  /api/v1    │   │  Dict[camera_id → StreamWorker]  │  │ │
│  │  └──────┬──────┘   └──────────────┬───────────────────┘  │ │
│  │         │                         │ one per camera        │ │
│  │  ┌──────▼──────┐   ┌──────────────▼───────────────────┐  │ │
│  │  │  MongoDB    │   │           StreamWorker            │  │ │
│  │  │  cameras    │   │  - cv2.VideoCapture(rtsp_url)     │  │ │
│  │  │  events     │   │  - SlidingWindowFPS calculator    │  │ │
│  │  └─────────────┘   │  - No-frame timeout detection     │  │ │
│  │                    │  - Auto-reconnect loop            │  │ │
│  │  ┌─────────────┐   │  - latest_frame: np.ndarray       │  │ │
│  │  │   MJPEG     │   └──────────────────────────────────┘  │ │
│  │  │  Endpoint   │◀── frame bytes                          │ │
│  │  └──────┬──────┘                                         │ │
│  │         │                   ┌──────────────────────────┐ │ │
│  │  ┌──────▼──────┐            │     AlertService         │ │ │
│  │  │   Browser   │            │  - Save to MongoDB       │ │ │
│  │  │  Dashboard  │◀── WS ────│  - Cooldown tracking     │ │ │
│  │  └─────────────┘            │  - Telegram (optional)   │ │ │
│  │                             └──────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Frame Reading Flow
```
MediaMTX (RTSP) → cv2.VideoCapture → StreamWorker
  → latest_frame (numpy array, in memory)
  → FPS Calculator (sliding window)
  → RuntimeStatus update (in memory only)
  → MJPEG endpoint reads latest_frame → JPEG encode → browser
```

### 2. Status Update Flow
```
StreamWorker (per-camera loop, every frame):
  → RuntimeStatus.actual_fps, frame_age_ms, uptime_seconds updated
  → No MongoDB write per frame

StreamManager.get_all_statuses():
  → Called by GET /api/v1/cameras (REST poll)
  → Called by WS /api/v1/ws/dashboard (push every 1s)
  → Returns merged config (MongoDB) + runtime (memory)
```

### 3. Failure/Reconnect Flow
```
Frame NOT received for > NO_FRAME_TIMEOUT_SECONDS (5s):
  status → DISCONNECTED
  → AlertService.emit(CAMERA_DISCONNECTED, CRITICAL)
    → StreamEventRepository.create() → MongoDB
    → WebSocketManager.broadcast() → browser toast
    → TelegramNotifier.send() (if enabled)
  status → RECONNECTING
  → sleep(RECONNECT_INTERVAL_SECONDS)
  → cv2.VideoCapture(rtsp_url) again
  → If connected: status → CONNECTED, emit CAMERA_RECONNECTED
```

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | App factory, lifespan, routing, static files |
| `core/config.py` | pydantic-settings, single source of truth |
| `core/logging.py` | dictConfig, per-module loggers |
| `core/constants.py` | Enums (CameraStatus, EventType, Severity) |
| `db/mongodb.py` | Motor client, connect/disconnect lifecycle |
| `db/indexes.py` | Create MongoDB indexes on startup |
| `models/` | MongoDB documents + RuntimeStatus dataclass |
| `schemas/` | Pydantic request/response validation |
| `repositories/` | Raw MongoDB CRUD (no business logic) |
| `services/stream_worker.py` | RTSP read loop, FPS, timeout, reconnect |
| `services/stream_manager.py` | Dict of workers, aggregate status, startup load |
| `services/camera_service.py` | Business logic, merge config+runtime |
| `services/alert_service.py` | Event persistence, cooldown, Telegram |
| `services/metrics_service.py` | psutil/pynvml, background threshold monitor |
| `services/websocket_manager.py` | WS connection set, broadcast |
| `api/v1/` | Route handlers per feature area |
| `utils/` | FPS calculator, time helpers, JPEG encoder |
| `web/` | Dashboard HTML/CSS/JS |

## Design Decisions

### Memory-first Runtime Status
Runtime data (FPS, frame_age, reconnect_count) is kept in `StreamWorker` memory, not written to MongoDB per frame. This avoids MongoDB write amplification and allows high-frequency updates without DB overhead.

### Asyncio + Executor for OpenCV
`cv2.VideoCapture.read()` is blocking. We use `loop.run_in_executor(None, cap.read)` to avoid blocking the event loop. The MJPEG generator and WebSocket broadcaster continue serving other clients while a frame is being decoded.

### API Versioning
All routes under `/api/v1/`. Adding v2 means creating `app/api/v2/` and mounting it in `main.py` — v1 is never modified.

### MJPEG vs WebRTC
MJPEG chosen for simplicity (no signaling, no STUN/TURN, works in any browser with `<img>`). For production, WebRTC or LL-HLS is recommended for lower latency and better scalability.
