# API Examples

## Base URL
```
http://localhost:8000/api/v1
```

## Camera CRUD

### Register Camera
```bash
curl -X POST http://localhost:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Camera 1",
    "rtsp_url": "rtsp://mediamtx:8554/cam1",
    "resolution": "640x360",
    "target_fps": 10,
    "display_fps": 5,
    "enabled": true,
    "description": "Main gate camera"
  }'
```

**Response (201):**
```json
{
  "id": "665f...",
  "name": "Camera 1",
  "rtsp_url": "rtsp://mediamtx:8554/cam1",
  "resolution": "640x360",
  "target_fps": 10,
  "display_fps": 5,
  "enabled": true,
  "status": "CONNECTING",
  "actual_fps": 0.0,
  "reconnect_count": 0
}
```

### List Cameras (Batch Status)
```bash
curl http://localhost:8000/api/v1/cameras
```

### Get One Camera
```bash
curl http://localhost:8000/api/v1/cameras/{camera_id}
```

### Update Camera
```bash
curl -X PUT http://localhost:8000/api/v1/cameras/{camera_id} \
  -H "Content-Type: application/json" \
  -d '{"name": "Entrance Camera", "display_fps": 10}'
```

### Delete Camera
```bash
curl -X DELETE http://localhost:8000/api/v1/cameras/{camera_id}
```

### Get Camera Status (Debug)
```bash
curl http://localhost:8000/api/v1/cameras/{camera_id}/status
```

### Update Display FPS (Hot Apply)
```bash
curl -X PATCH http://localhost:8000/api/v1/cameras/{camera_id}/display-fps \
  -H "Content-Type: application/json" \
  -d '{"display_fps": 10}'
```

## Stream

### MJPEG Video Stream (use in browser img tag)
```
GET http://localhost:8000/api/v1/streams/{camera_id}/mjpeg
```
```html
<img src="http://localhost:8000/api/v1/streams/665f.../mjpeg" />
```

## System Metrics

```bash
curl http://localhost:8000/api/v1/system/metrics
```

**Response:**
```json
{
  "cpu_percent": 42.5,
  "memory_percent": 61.2,
  "memory_used_mb": 8200.0,
  "gpu_available": false,
  "gpu_percent": null,
  "gpu_memory_used_mb": null,
  "active_streams": 4
}
```

## Stream Events

```bash
# All recent events
curl http://localhost:8000/api/v1/stream-events

# Filter by camera
curl "http://localhost:8000/api/v1/stream-events?camera_id={id}"

# Filter by severity
curl "http://localhost:8000/api/v1/stream-events?severity=CRITICAL&limit=10"

# Filter by event type
curl "http://localhost:8000/api/v1/stream-events?event_type=CAMERA_DISCONNECTED"
```

## WebSocket Dashboard

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/dashboard');
ws.onmessage = (evt) => {
  const msg = JSON.parse(evt.data);
  switch (msg.type) {
    case 'camera_status_snapshot': // every 1s
      console.log('Cameras:', msg.data);
      break;
    case 'system_metrics':          // every 3s
      console.log('Metrics:', msg.data);
      break;
    case 'stream_event':            // on event
      console.log('Event:', msg.data);
      break;
  }
};
```
