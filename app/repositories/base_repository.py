"""Reusable async MongoDB CRUD operations for repositories."""
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.common.serializers import serialize_mongo_document


class BaseRepository:
    """Base class for MongoDB persistence; domain queries remain in subclasses."""

    collection_name: str

    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[self.collection_name]

    async def insert_one(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        result = await self.col.insert_one(payload)
        document = await self.col.find_one({"_id": result.inserted_id})
        return serialize_mongo_document(document) or {}

    async def get_by_id(self, document_id: str) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(document_id):
            return None
        document = await self.col.find_one({"_id": ObjectId(document_id)})
        return serialize_mongo_document(document)

    async def update_by_id(self, document_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(document_id):
            return None
        await self.col.update_one({"_id": ObjectId(document_id)}, {"$set": dict(data)})
        return await self.get_by_id(document_id)

    async def delete_by_id(self, document_id: str) -> bool:
        if not ObjectId.is_valid(document_id):
            return False
        result = await self.col.delete_one({"_id": ObjectId(document_id)})
        return result.deleted_count > 0

    @staticmethod
    def with_timestamps(data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        now = datetime.utcnow()
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        return payload

    @staticmethod
    def with_updated_timestamp(data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        payload["updated_at"] = datetime.utcnow()
        return payload
