"""
Runtime status model — held in memory inside StreamManager.

NOT stored in MongoDB every second. Only persisted when important events happen.

Updated for HLS/MediaMTX architecture:
- Removed frame_age_ms (no frame buffer in Python anymore)
- Status is derived from MediaMTX API polling, not OpenCV frame reads
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from app.core.constants import CameraStatus


@dataclass
class RuntimeStatus:
    """In-memory runtime state for one camera stream (MediaMTX-backed)."""
    camera_id: str
    status: CameraStatus = CameraStatus.CREATED
    actual_fps: float = 0.0
    display_fps: int = 5
    latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    last_frame_at: Optional[datetime] = None
    last_connected_at: Optional[datetime] = None
    last_disconnected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    simulated_offline: bool = False
    reconnect_timeout_alerted: bool = False  # True after emitting the 10s-no-reconnect alert

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "status": self.status.value if isinstance(self.status, CameraStatus) else self.status,
            "actual_fps": round(self.actual_fps, 2),
            "display_fps": self.display_fps,
            "latency_ms": round(self.latency_ms, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "reconnect_count": self.reconnect_count,
            "last_frame_at": self.last_frame_at.isoformat() if self.last_frame_at else None,
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None,
            "last_disconnected_at": self.last_disconnected_at.isoformat() if self.last_disconnected_at else None,
            "last_error": self.last_error,
            "simulated_offline": self.simulated_offline,
        }
