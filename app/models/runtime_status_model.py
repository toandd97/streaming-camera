"""
Runtime status model — held in memory inside StreamWorker/StreamManager.

NOT stored in MongoDB every second. Only persisted when important events happen.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from app.core.constants import CameraStatus


@dataclass
class RuntimeStatus:
    """In-memory runtime state for one camera stream."""
    camera_id: str
    status: CameraStatus = CameraStatus.CREATED
    actual_fps: float = 0.0
    display_fps: int = 5
    latency_ms: float = 0.0
    frame_age_ms: float = 0.0
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    last_frame_at: Optional[datetime] = None
    last_connected_at: Optional[datetime] = None
    last_disconnected_at: Optional[datetime] = None
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "status": self.status.value,
            "actual_fps": round(self.actual_fps, 2),
            "display_fps": self.display_fps,
            "latency_ms": round(self.latency_ms, 2),
            "frame_age_ms": round(self.frame_age_ms, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "reconnect_count": self.reconnect_count,
            "last_frame_at": self.last_frame_at.isoformat() if self.last_frame_at else None,
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None,
            "last_disconnected_at": self.last_disconnected_at.isoformat() if self.last_disconnected_at else None,
            "last_error": self.last_error,
        }
