"""
Camera MongoDB document model.

Note: Runtime status is NOT stored here — it lives in StreamManager memory.
This model only stores persistent configuration.
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        schema.update(type="string")
        return schema


class CameraDocument(BaseModel):
    """Represents a camera document in the 'cameras' MongoDB collection."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str
    rtsp_url: str
    resolution: str = "640x360"
    target_fps: int = 10
    display_fps: int = 5
    enabled: bool = True
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
