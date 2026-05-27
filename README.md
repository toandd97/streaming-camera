# ORBRO B1 — Camera Management & Streaming Video System

> **ORBRO Vina Backend Developer Test — B1**
> Stack: FastAPI + MongoDB + MediaMTX + FFmpeg + HLS Web UI

> **English Summary:** This project implements a real-time Video Management System (VMS) capable of displaying and managing 4 to 80 RTSP camera streams. It utilizes FastAPI for metadata orchestration, MongoDB for data persistence, and MediaMTX to convert RTSP inputs into HLS streams. The architecture optimizes server resources by polling MediaMTX for connection status instead of decoding frames in Python, and limits client CPU usage by visually throttling HLS frame rates via an HTML5 Canvas `requestAnimationFrame` loop. It also includes an auto-reconnect mechanism and integrates Telegram for real-time alerting on camera disconnections and server resource spikes.

---

## Table of Contents
1. [Problem Statement](#1-problem-statement)
2. [System Architecture](#2-system-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Folder Structure](#4-folder-structure)
5. [API Design](#5-api-design)
6. [Database Schema](#6-database-schema)
7. [Main Processing Flows](#7-main-processing-flows)
8. [How to Run](#8-how-to-run)
9. [How to Test](#9-how-to-test)
10. [Operational Considerations](#10-operational-considerations)
11. [AI Usage & Verification](#11-ai-usage--verification)

---

## 1. Problem Statement

The requirement is to build a real-time **Video Management System (VMS)** with the following core requirements:
* **Visual Monitoring:** Simultaneously display video streams from multiple cameras in a minimum 4-cell Grid layout on a web interface. The system must be scalable to handle 32-80 channels.
* **RTSP Source Simulation:** Loop an existing video file to simulate RTSP streams in a local environment.
* **Camera Management (CRUD):** Provide APIs to register, query, modify, and delete cameras.
* **Status Monitoring:** Detect physical camera stream disconnections, automatically attempt to reconnect (auto-reconnect) continuously, log events and reconnect counts to MongoDB, and display real-time uptime.
* **Alerts (Telegram + UI):** Send alerts via Telegram Bot API and the Web interface when a camera loses connection for more than 10 seconds or when server resources (CPU, RAM) exceed allowed thresholds.
* **Dynamic FPS Adjustment:** Allow independent adjustment of the display FPS for each camera cell on the grid. This configuration change must be applied immediately to the screen without restarting the RTSP stream.

---

## 2. System Architecture

The system is designed with a separation between the Control Path and the Data Path to maximize performance and scalability:

```text
resources/videos/*.mp4 → demo-publisher (FFmpeg loop, stream-copy) → MediaMTX (RTSP)
                                                                          ├── HLS → Browser tiles (Canvas)
                                                                          └── API → FastAPI StreamManager poller
FastAPI (:8000) ── Camera CRUD / MongoDB / Metrics / Alerts / WebSocket UI updates ── Browser (UI)
```

### Core Design Decisions:
1. **Avoid Frame Decoding on Backend (FastAPI):** Decoding individual RTSP video frames using the OpenCV library in Python consumes extremely high CPU resources. The system replaces this by delegating stream processing to **MediaMTX**. FastAPI only periodically polls MediaMTX's API (every 5s) to monitor the connection status and uptime of the streams. Consequently, the backend can scale to 80+ streams with minimal CPU/RAM usage.
2. **Client-Side Visual FPS Throttling (Canvas Render):** HLS video is delivered directly from MediaMTX to the browser via the `hls.js` library. To support dynamic FPS changes without running an encoder on the server, the Web UI hides the `<video>` tag and draws frames onto a corresponding `<canvas>` tag using a `requestAnimationFrame` loop. This loop throttles the drawing frequency to match the configured FPS for each cell, optimizing the client device's CPU load.
3. **Simulation Mode:** Provides "Sim Off" (simulate disconnection) and "Sim On" (restore connection) buttons. These simulated tasks run asynchronously on the backend and automatically restore the camera connection after 15 seconds if the user does not manually click reconnect beforehand.

---

## 3. Tech Stack

| Component | Technology Used | Role |
|-----------|-----------------|------|
| **Backend Framework** | Python 3.11, FastAPI, Uvicorn | Build REST APIs and WebSockets, manage background tasks |
| **Database** | MongoDB 7, Motor | Store static camera configurations and asynchronous system events |
| **RTSP Media Server** | MediaMTX (bluenviron) | Receive incoming RTSP streams, output packaged HLS, and provide status REST API |
| **RTSP Publisher** | FFmpeg | Loop `.mp4` video files from resources and push (stream-copy) to MediaMTX |
| **Frontend UI** | Vanilla HTML, CSS, JS | Dashboard displaying camera grid, resource charts, and event logs |
| **HLS Player** | HLS.js | Decode and play HLS videos directly in the browser |
| **Alerting Channel** | Telegram Bot API | Send alert messages for connection issues and system resource overloads |
| **Deployment** | Docker & Docker Compose | Package and run all services in isolated environments |

---

## 4. Folder Structure

```
streaming-camera/
├── app/
│   ├── main.py              # FastAPI entry point, registers routers and startup/shutdown events
│   ├── common/              # MongoDB serializers and common API response schemas
│   ├── core/                # Environment configuration (Pydantic settings), logging, and system constants
│   ├── api/
│   │   └── v1/              # Fragmented routing: camera, stream, event, metrics, websocket
│   ├── db/                  # MongoDB database setup and teardown
│   ├── models/              # Database schema definitions (Camera, Event) and RuntimeStatus
│   ├── schemas/             # Pydantic schemas for request/response validation
│   ├── repositories/        # DB interaction layer (BaseRepository CRUD and CameraRepository)
│   ├── services/            # Business logic: StreamManager, AlertService, TelegramNotifier, Metrics
│   ├── utils/               # Utilities: generating placeholder images on error, FPS counting
│   └── web/                 # Dashboard UI: index.html, styles.css, app.js
├── scripts/                 # Scripts to help setup the environment and run tests
├── resources/               # Sample resources (videos, images, excel)
├── docs/                    # Architecture documentation, AI usage logs, and PlantUML flows
├── Dockerfile               # Dockerfile for building the FastAPI application
├── docker-compose.yml       # Service orchestration (mongo, mediamtx, app, demo-publisher)
├── setup.sh                 # Quick setup script for the entire system
└── requirements.txt         # Python dependency declarations
```

---

## 5. API Design

The application provides standard REST APIs for camera management and system monitoring under the `/api/v1` prefix:

### 5.1 Camera Management (CRUD)

* **`POST /api/v1/cameras`**
  - **Description:** Register a new camera into the system and activate stream monitoring.
  - **Payload:**
    ```json
    {
      "name": "Camera Garden",
      "rtsp_url": "rtsp://mediamtx:8554/demo/garden",
      "resolution": "640x360",
      "target_fps": 10,
      "display_fps": 15,
      "enabled": true
    }
    ```
  - **Response (201 Created):** Returns the created camera information along with its storage ID.

* **`GET /api/v1/cameras`**
  - **Description:** Retrieve the list of all cameras; the result automatically merges the configuration information from the database with the actual runtime status from memory.
  - **Response (200 OK):**
    ```json
    [
      {
        "id": "6472d73f1d2e3f4a5b6c7d8e",
        "name": "Camera Garden",
        "rtsp_url": "rtsp://mediamtx:8554/demo/garden",
        "resolution": "640x360",
        "target_fps": 10,
        "display_fps": 15,
        "enabled": true,
        "status": "CONNECTED",
        "uptime_seconds": 124.5,
        "reconnect_count": 0,
        "simulated_offline": false
      }
    ]
    ```

* **`GET /api/v1/cameras/{camera_id}`**
  - **Description:** Retrieve detailed configuration and runtime status information for a specific camera.

* **`PUT /api/v1/cameras/{camera_id}`**
  - **Description:** Update the entire camera configuration.
  - **Note:** If the `rtsp_url` is changed, the system will automatically restart the monitoring stream. If only the name or `display_fps` is changed, the monitoring stream remains uninterrupted.

* **`DELETE /api/v1/cameras/{camera_id}`**
  - **Description:** Stop monitoring and delete the camera configuration from the database.

* **`GET /api/v1/cameras/{camera_id}/status`**
  - **Description:** Retrieve only the current runtime status information of the camera (for debugging purposes).

* **`PATCH /api/v1/cameras/{camera_id}/display-fps`**
  - **Description:** Hot-update the camera's display FPS configuration. This change is applied immediately without disconnecting the RTSP stream.
  - **Payload:**
    ```json
    {
      "display_fps": 30
    }
    ```

### 5.2 Streams & Metrics

* **`GET /api/v1/streams/{camera_id}/hls-info`**
  - **Description:** Returns the HLS URL for the browser UI to load into the player.
  - **Response (200 OK):**
    ```json
    {
      "camera_id": "6472d73f1d2e3f4a5b6c7d8e",
      "hls_url": "http://localhost:8888/demo/garden/index.m3u8",
      "rtsp_path": "demo/garden",
      "available": true
    }
    ```

* **`GET /api/v1/system/metrics`**
  - **Description:** Retrieve real-time hardware metrics of the server (CPU, RAM, GPU if available).

* **`GET /api/v1/stream-events`**
  - **Description:** Retrieve the history of the 50 most recent system anomaly events stored in the database.

### 5.3 WebSocket Real-time Push

* **`WS /api/v1/ws/dashboard`**
  - **Description:** WebSocket endpoint connected from the Web Dashboard interface. The server proactively pushes updates:
    - Camera status snapshots (`camera_status_snapshot`) periodically every 1 second.
    - System resource alerts (`system_metrics`) periodically every 3 seconds.
    - Immediately pushes camera error/reconnect events as soon as they occur.

---

## 6. Database Schema

The system uses a MongoDB database for persistent data storage, combined with in-memory storage (RAM) for runtime status to ensure maximum performance.

### 6.1 Cameras Collection (`cameras`)
Stores registered camera configurations:
```json
{
  "_id": "ObjectId",
  "name": "string",
  "rtsp_url": "string",
  "resolution": "string (default: '640x360')",
  "target_fps": "int (default: 10)",
  "display_fps": "int (default: 5)",
  "enabled": "boolean (default: true)",
  "description": "string (optional)",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### 6.2 Stream Events Collection (`stream_events`)
Stores connection incident logs and resource overload system alerts:
```json
{
  "_id": "ObjectId",
  "camera_id": "string",
  "event_type": "string (CAMERA_DISCONNECTED, CAMERA_RECONNECTED, RECONNECT_TIMEOUT, HIGH_CPU, HIGH_MEMORY)",
  "severity": "string (INFO, WARNING, ERROR, CRITICAL)",
  "message": "string",
  "metric_name": "string (optional)",
  "metric_value": "double (optional)",
  "threshold": "double (optional)",
  "notified": "boolean (default: false - indicates whether the Telegram alert was successfully sent)",
  "created_at": "ISODate"
}
```

### 6.3 In-memory Runtime Status (`RuntimeStatus`)
This operational status information is stored entirely in the RAM of the `StreamManager` class to continuously record data without causing disk write bottlenecks:
* `camera_id` (string)
* `status` (Enum: CREATED, CONNECTED, DISCONNECTED, RECONNECTING)
* `actual_fps` (float)
* `display_fps` (int)
* `uptime_seconds` (float)
* `reconnect_count` (int)
* `last_connected_at` (datetime)
* `last_disconnected_at` (datetime)
* `simulated_offline` (boolean)
* `reconnect_timeout_alerted` (boolean)

---

## 7. Main Processing Flows

The detailed business flows of the system include:
1. **Camera Registration & HLS Video Playback Flow**
2. **Monitoring & Auto-Reconnect Flow (Disconnections >10s trigger Telegram alerts)**
3. **Telegram Alert & Cooldown Mechanism Flow (To prevent notification spam)**
4. **Client-Side Canvas Visual FPS Throttling Flow**

> [!TIP]
> To view detailed descriptions and Sequence Diagrams drawn with **PlantUML** for all 4 business flows, please visit the documentation file:
> 👉 **[System Processing Flows Documentation (PlantUML)](docs/processing_flows.md)**

---

## 8. How to Run

The system provides a fully automated setup script to configure the environment, download sample videos, build Docker images, and register demo cameras.

### Prerequisites
Ensure your computer has the following tools installed:
- **Docker** (v20.10 or higher) and **Docker Compose** (v2.0 or higher).
- **curl** (to check API connections and run automated scripts).
- **bash shell** (If on Windows, use WSL (if use Window) or Git Bash).

---

### 🚀 One-Command Setup (Recommended)

**Step 1: Clone the source code and enter the directory**
```bash
git clone <repo-url> camera-monitoring
cd camera-monitoring
```

**Step 2: Run the setup script**
```bash
bash setup.sh
```

**Steps handled automatically by the script:**
1. Initializes the `.env` configuration file if it does not exist.
2. Checks for sample video resources at `resources/videos/`. If absent, automatically downloads a test video (`Big Buck Bunny`, lightweight ~1MB).
3. Builds and starts service containers: `orbro_mongo`, `orbro_mediamtx`, `streaming-camera-app`.
4. Polls the FastAPI health check API until the service is ready.
5. Starts the `demo-publisher` container for FFmpeg to loop the video, creating 4 corresponding RTSP streams.
6. Automatically registers 4 cameras into MongoDB via the project's API.

**Step 3: Open the Dashboard**
Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

### How to Verify the System is Running Correctly
1. **Check Container Status:**
   The command `docker compose ps` must show all 4 containers (`streaming-camera-app`, `orbro_mediamtx`, `orbro_mongo`, `orbro_demo_publisher`) in an `Up` or `running` state.
2. **Check API Results:**
   Running `curl http://localhost:8000/api/v1/cameras` should return a JSON list of 4 cameras with `"status": "CONNECTED"`.

---

## 9. How to Test

### 9.1 Run Automated Unit Tests (Pytest)
The project is built with comprehensive automated test scenarios, particularly covering the auto-reconnect behaviors and the cancellation of background tasks upon manual recovery.

Activate the environment and run tests:
```bash
pip install -r requirements.txt
pytest tests/ -v
```

### 9.2 Manual Testing of Simulation Features
Open the Dashboard at `http://localhost:8000` and perform visual tests:

1. **Simulate Camera Disconnection and Auto-Recovery:**
   - Select any camera and click the **`Sim Off`** button.
   - **Observe UI:** The camera status immediately changes to `RECONNECTING` (Yellow color).
   - **Verify Auto-Reconnect:** After exactly 15 seconds, the camera will automatically revert to the `CONNECTED` state (Green color), and the video will resume playing normally without reloading the page.
   - **Verify 10-Second Alert:** If you wish to test the Telegram alert when a camera is disconnected for over 10 seconds: You can manually turn off the source stream publisher by running `docker compose --profile demo stop demo-publisher`. Wait 10 seconds, then check the system logs or your Telegram messages to see that the disconnection alert has been sent.
2. **Simulate System Resource Overload:**
   - Scroll down to the **Simulation Panel** on the right sidebar.
   - Click the **`Simulate High CPU`** or **`Simulate High RAM`** buttons.
   - Observe the event log at the bottom of the screen and check your Telegram messages to confirm the alert was sent successfully.

---

## 10. Operational Considerations

### 10.1 Scaling Bottlenecks (From 8 to 80 Channels)
When upgrading the monitoring system from a small number to a large scale (80+ cameras), system bottlenecks may occur at:
1. **Network Bandwidth:** 80 HLS streams playing simultaneously on the user's Web interface will cause network congestion. The solution is to apply **Lazy Loading** (only playing HLS when that camera cell is visible on the user's screen, and pausing when scrolled out of view).
2. **FFmpeg Decoding and Streaming Process:** Running 80 FFmpeg processes to simulate RTSP consumes substantial CPU. The practical solution is using real IP camera hardware to transmit RTSP directly to MediaMTX, completely freeing up the simulated FFmpeg processes.
3. **Disk Write I/O:** Writing too many event logs to MongoDB. This is mitigated by only updating the runtime status in RAM (`StreamManager`), and only writing to MongoDB when the camera's connection status actually changes.
4. **Browser Connection Limits:** Most browsers limit concurrent HTTP/1.1 connections to the same domain to 6. It is necessary to configure the **HTTP/2** protocol for MediaMTX to concurrently transmit dozens of HLS video streams to a single browser without connection bottlenecks.

### 10.2 Handling Stream Disconnections and Decoder Hangs
* The monitoring system of `StreamManager` features a mechanism to detect data-loss streams via MediaMTX's API.
* When the input RTSP stream is interrupted, MediaMTX closes the path, and FastAPI immediately detects this to transition the camera into a `RECONNECTING` state.
* If the client-side decoder (HLS.js) hangs or freezes, the Dashboard frontend has an event-detection mechanism for frozen/errored streams and will automatically recall the `startHLS()` initialization function to recover the player.

### 10.3 Performance Measurement Environment
All performance metrics and scaling considerations must be evaluated against the actual hardware environment. When submitting or verifying this system, the following hardware specifications have been logged:
- **OS:** Ubuntu 22.04.5 LTS
- **CPU:** Intel Core i5-1135G7 @ 2.40GHz
- **RAM:** 16 GB
- **GPU:** Intel Iris Xe Graphics
*(Detailed measurement results can be found in `docs/measurement_result.md` and `docs/report.md`)*

---

## 11. AI Usage & Verification

This project was designed and realized with close collaboration between the developer and an AI assistant (Google DeepMind Antigravity).

### 11.1 AI Assistance Roles:
- **Source Code Scaffolding:** Rapidly initialized a standard FastAPI directory structure, set up the Dockerfile, and created the `docker-compose.yml` orchestration file with built-in health check mechanisms for MongoDB.
- **Algorithm Optimization Implementation:** Created a high-performance Sliding Winhdow FPS counter and a solution to render video streams via Canvas instead of video tags to support custom FPS throttling on the client.
- **Automated Testing Generation:** Created comprehensive unit test files covering the asynchronous multi-threaded testing behaviors of the `StreamManager`.

### 11.2 Areas Requiring Human Intervention and Control:
- **Determining State Storage Mechanisms:** Clearly dividing the storage of static configuration in MongoDB and the continuously changing operational state in RAM to optimize disk I/O.
- **Fixing Stale Closure Errors on Frontend:** When updating the camera list in real-time, UI click events retained references to old, freed camera objects. The developer refined the logic to dynamically search for the camera object within the `cameras` array at the time of the click, completely resolving the issue where Sim On/Off buttons failed to change state after interaction.
- **HLS URL Synchronization:** Fixed the issue where WebSocket status update packets overwrote and erased the camera's `hls_url` path on the interface, which previously prevented the player from automatically resuming playback after the camera came back online.

*For a detailed overview of the entire interaction process, please refer to the documents:*
- 📄 **[AI Tool Usage Log](docs/ai_usage_log.md)**
- 📄 **[AI Retrospective and Improvement Report](docs/ai_retrospective.md)**
 
Video Demo:
(../resources/video_demo.webm)
telegram_demo:
![telegram_demo](../resources/images/telegram_demo.png)