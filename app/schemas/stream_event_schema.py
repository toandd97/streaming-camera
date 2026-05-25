from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.core.constants import EventType, Severity


class StreamEventResponse(BaseModel):
    id: str
    camera_id: str
    event_type: EventType
    severity: Severity
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    notified: bool
    created_at: datetime
