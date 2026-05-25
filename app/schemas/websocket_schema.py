"""
WebSocket message schemas for dashboard real-time updates.
"""
from typing import Any, List, Optional
from pydantic import BaseModel
from app.core.constants import WS_CAMERA_STATUS_SNAPSHOT, WS_SYSTEM_METRICS, WS_STREAM_EVENT


class WsMessage(BaseModel):
    """Base WebSocket message envelope."""
    type: str
    data: Any


class WsCameraStatusSnapshot(BaseModel):
    """Sent every 1 second: all camera statuses."""
    type: str = WS_CAMERA_STATUS_SNAPSHOT
    data: List[dict]


class WsSystemMetrics(BaseModel):
    """Sent every 2-5 seconds: CPU/RAM/GPU."""
    type: str = WS_SYSTEM_METRICS
    data: dict


class WsStreamEvent(BaseModel):
    """Sent immediately when a stream event occurs."""
    type: str = WS_STREAM_EVENT
    data: dict
