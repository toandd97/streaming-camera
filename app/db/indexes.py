"""
MongoDB index creation at startup.

Called once after MongoDB connection is established to ensure
optimal query performance for cameras and stream_events collections.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create all required indexes for the application."""
    logger.info("Creating MongoDB indexes...")

    # cameras collection
    await db.cameras.create_index([("name", ASCENDING)])
    await db.cameras.create_index([("enabled", ASCENDING)])
    await db.cameras.create_index([("created_at", DESCENDING)])

    # stream_events collection
    await db.stream_events.create_index([("camera_id", ASCENDING)])
    await db.stream_events.create_index([("event_type", ASCENDING)])
    await db.stream_events.create_index([("severity", ASCENDING)])
    await db.stream_events.create_index([("created_at", DESCENDING)])
    # Compound index for typical dashboard queries
    await db.stream_events.create_index([
        ("camera_id", ASCENDING),
        ("created_at", DESCENDING)
    ])

    logger.info("MongoDB indexes created successfully")
