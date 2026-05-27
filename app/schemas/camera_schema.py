"""
Pydantic schemas for Camera API — request/response validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.core.constants import CameraStatus, ALLOWED_DISPLAY_FPS


class CameraCreate(BaseModel):
    """POST /api/v1/cameras request body."""
    name: str = Field(..., min_length=1, max_length=100)
    rtsp_url: str = Field(..., min_length=1)
    resolution: str = "640x360"
    target_fps: int = Field(default=10, ge=1, le=60)
    display_fps: int = Field(default=5, ge=1, le=120)
    enabled: bool = True
    description: Optional[str] = None

    @field_validator("display_fps")
    @classmethod
    def display_fps_must_be_allowed(cls, v: int) -> int:
        if v not in ALLOWED_DISPLAY_FPS:
            raise ValueError(f"display_fps must be one of {ALLOWED_DISPLAY_FPS}")
        return v

    @field_validator("rtsp_url")
    @classmethod
    def rtsp_url_must_be_valid(cls, v: str) -> str:
        allowed_protocols = ("rtsp://", "rtmp://", "http://", "https://")
        allowed_file_prefixes = ("/", "./", "../")
        allowed_file_extensions = (".mp4", ".avi", ".mkv", ".mov")
        
        starts_with_protocol = any(v.startswith(p) for p in allowed_protocols)
        starts_with_file_prefix = any(v.startswith(p) for p in allowed_file_prefixes)
        ends_with_video_ext = any(v.lower().endswith(ext) for ext in allowed_file_extensions)
        
        if not (starts_with_protocol or starts_with_file_prefix or ends_with_video_ext):
            raise ValueError(
                "RTSP URL must start with rtsp://, rtmp://, http://, or https:// (or refer to a local video file)"
            )
        return v


class CameraUpdate(BaseModel):
    """PUT /api/v1/cameras/{id} request body."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    rtsp_url: Optional[str] = None
    resolution: Optional[str] = None
    target_fps: Optional[int] = Field(default=None, ge=1, le=60)
    display_fps: Optional[int] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None

    @field_validator("display_fps")
    @classmethod
    def display_fps_must_be_allowed(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in ALLOWED_DISPLAY_FPS:
            raise ValueError(f"display_fps must be one of {ALLOWED_DISPLAY_FPS}")
        return v

    @field_validator("rtsp_url")
    @classmethod
    def rtsp_url_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed_protocols = ("rtsp://", "rtmp://", "http://", "https://")
        allowed_file_prefixes = ("/", "./", "../")
        allowed_file_extensions = (".mp4", ".avi", ".mkv", ".mov")
        
        starts_with_protocol = any(v.startswith(p) for p in allowed_protocols)
        starts_with_file_prefix = any(v.startswith(p) for p in allowed_file_prefixes)
        ends_with_video_ext = any(v.lower().endswith(ext) for ext in allowed_file_extensions)
        
        if not (starts_with_protocol or starts_with_file_prefix or ends_with_video_ext):
            raise ValueError(
                "RTSP URL must start with rtsp://, rtmp://, http://, or https:// (or refer to a local video file)"
            )
        return v


class DisplayFpsUpdate(BaseModel):
    """PATCH /api/v1/cameras/{id}/display-fps request body."""
    display_fps: int

    @field_validator("display_fps")
    @classmethod
    def display_fps_must_be_allowed(cls, v: int) -> int:
        if v not in ALLOWED_DISPLAY_FPS:
            raise ValueError(f"display_fps must be one of {ALLOWED_DISPLAY_FPS}")
        return v


class CameraResponse(BaseModel):
    """Full camera response — config merged with runtime status."""
    id: str
    name: str
    rtsp_url: str
    resolution: str
    target_fps: int
    display_fps: int
    enabled: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # HLS stream URL (served by MediaMTX, used by frontend hls.js)
    hls_url: Optional[str] = None
    # Runtime fields (from StreamManager memory, updated by MediaMTX poller)
    status: str = CameraStatus.CREATED.value
    actual_fps: float = 0.0
    latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    last_frame_at: Optional[str] = None
    last_connected_at: Optional[str] = None
    last_disconnected_at: Optional[str] = None
    last_error: Optional[str] = None
    simulated_offline: bool = False

