from typing import Optional
from pydantic import BaseModel


class SystemMetricsResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    gpu_available: bool
    gpu_percent: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None
    active_streams: int


class TelegramConfigUpdate(BaseModel):
    bot_token: Optional[str] = None
    chat_id: str


class TelegramConfigResponse(BaseModel):
    enabled: bool
    token_configured: bool
    chat_id: str
    project: str
