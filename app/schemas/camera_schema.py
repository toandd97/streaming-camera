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
    display_fps: int = Field(default=5, ge=1, le=15)
    enabled: bool = True
    description: Optional[str] = None

    @field_validator("display_fps")
    @classmethod
    def display_fps_must_be_allowed(cls, v: int) -> int:
        if v not in ALLOWED_DISPLAY_FPS:
            raise ValueError(f"display_fps must be one of {ALLOWED_DISPLAY_FPS}")
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
    # Runtime fields (from StreamManager memory)
    status: str = CameraStatus.CREATED.value
    actual_fps: float = 0.0
    latency_ms: float = 0.0
    frame_age_ms: float = 0.0
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    last_frame_at: Optional[str] = None
    last_connected_at: Optional[str] = None
    last_disconnected_at: Optional[str] = None
    last_error: Optional[str] = None
