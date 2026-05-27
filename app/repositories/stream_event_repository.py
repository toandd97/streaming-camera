"""
StreamEvent repository — direct MongoDB access for the 'stream_events' collection.
"""
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.common.serializers import serialize_mongo_document
from app.repositories.base_repository import BaseRepository


class StreamEventRepository(BaseRepository):
    collection_name = "stream_events"

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)

    async def create(self, data: dict) -> dict:
        return await self.insert_one(data)

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
        return [serialize_mongo_document(d) for d in docs]
