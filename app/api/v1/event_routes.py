"""
Stream events endpoint — /api/v1/stream-events
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_database
from app.repositories.stream_event_repository import StreamEventRepository
from app.schemas.stream_event_schema import StreamEventResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stream-events", tags=["events"])


@router.get("", response_model=List[StreamEventResponse])
async def list_stream_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    List recent stream events from MongoDB.
    Supports filtering by camera_id, event_type, severity.
    """
    repo = StreamEventRepository(db)
    events = await repo.list_events(
        camera_id=camera_id,
        event_type=event_type,
        severity=severity,
        limit=limit,
    )
    # Convert datetime objects to strings
    for evt in events:
        if "created_at" in evt and hasattr(evt["created_at"], "isoformat"):
            evt["created_at"] = evt["created_at"].isoformat()
    return events
