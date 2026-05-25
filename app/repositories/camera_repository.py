"""
Camera repository — direct MongoDB access for the 'cameras' collection.

All methods return plain dicts or None. Business logic lives in camera_service.py.
"""
import logging
from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


def _serialize(doc: dict) -> dict:
    """Convert ObjectId _id to string id."""
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


class CameraRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.cameras

    async def create(self, data: dict) -> dict:
        now = datetime.utcnow()
        data["created_at"] = now
        data["updated_at"] = now
        result = await self.col.insert_one(data)
        doc = await self.col.find_one({"_id": result.inserted_id})
        return _serialize(doc)

    async def get_by_id(self, camera_id: str) -> Optional[dict]:
        if not ObjectId.is_valid(camera_id):
            return None
        doc = await self.col.find_one({"_id": ObjectId(camera_id)})
        return _serialize(doc) if doc else None

    async def list_all(self) -> list[dict]:
        cursor = self.col.find({}).sort("created_at", 1)
        docs = await cursor.to_list(length=None)
        return [_serialize(d) for d in docs]

    async def list_enabled(self) -> list[dict]:
        cursor = self.col.find({"enabled": True}).sort("created_at", 1)
        docs = await cursor.to_list(length=None)
        return [_serialize(d) for d in docs]

    async def update(self, camera_id: str, data: dict) -> Optional[dict]:
        if not ObjectId.is_valid(camera_id):
            return None
        data["updated_at"] = datetime.utcnow()
        await self.col.update_one(
            {"_id": ObjectId(camera_id)},
            {"$set": data}
        )
        return await self.get_by_id(camera_id)

    async def delete(self, camera_id: str) -> bool:
        if not ObjectId.is_valid(camera_id):
            return False
        result = await self.col.delete_one({"_id": ObjectId(camera_id)})
        return result.deleted_count > 0
