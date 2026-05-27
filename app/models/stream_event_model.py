"""
StreamEvent MongoDB document model.

Stores important events: disconnections, reconnections, low FPS, high CPU/RAM.
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from app.models.camera_model import PyObjectId
from app.core.constants import EventType, Severity


class StreamEventDocument(BaseModel):
    """Represents a document in the 'stream_events' MongoDB collection."""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    camera_id: str  # stringified ObjectId of the camera
    event_type: EventType
    severity: Severity
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    notified: bool = False  # True if Telegram notification was sent
    created_at: datetime = Field(default_factory=datetime.utcnow)
