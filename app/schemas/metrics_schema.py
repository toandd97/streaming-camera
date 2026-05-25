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
