"""
Camera repository — direct MongoDB access for the 'cameras' collection.

All methods return plain dicts or None. Business logic lives in camera_service.py.
"""
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.common.serializers import serialize_mongo_document
from app.repositories.base_repository import BaseRepository


class CameraRepository(BaseRepository):
    collection_name = "cameras"

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)

    async def create(self, data: dict) -> dict:
        return await self.insert_one(self.with_timestamps(data))

    async def list_all(self) -> list[dict]:
        cursor = self.col.find({}).sort("created_at", 1)
        docs = await cursor.to_list(length=None)
        return [serialize_mongo_document(d) for d in docs]

    async def list_enabled(self) -> list[dict]:
        cursor = self.col.find({"enabled": True}).sort("created_at", 1)
        docs = await cursor.to_list(length=None)
        return [serialize_mongo_document(d) for d in docs]

    async def update(self, camera_id: str, data: dict) -> Optional[dict]:
        return await self.update_by_id(camera_id, self.with_updated_timestamp(data))

    async def delete(self, camera_id: str) -> bool:
        return await self.delete_by_id(camera_id)
