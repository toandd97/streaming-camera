"""
StreamEvent repository — direct MongoDB access for the 'stream_events' collection.
"""
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


class StreamEventRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.stream_events

    async def create(self, data: dict) -> dict:
        result = await self.col.insert_one(data)
        doc = await self.col.find_one({"_id": result.inserted_id})
        return _serialize(doc)

    async def list_events(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        query: dict = {}
        if camera_id:
            query["camera_id"] = camera_id
        if event_type:
            query["event_type"] = event_type
        if severity:
            query["severity"] = severity

        cursor = self.col.find(query).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_serialize(d) for d in docs]
