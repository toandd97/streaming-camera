"""
MongoDB connection management using Motor (async driver).

Usage:
    from app.db.mongodb import get_database
    db = get_database()
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """Initialize MongoDB connection. Called at app startup."""
    global _client, _db
    logger.info("Connecting to MongoDB at %s", settings.mongo_uri)
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db_name]
    # Ping to verify connection
    await _client.admin.command("ping")
    logger.info("MongoDB connected — database: %s", settings.mongo_db_name)


async def close_db() -> None:
    """Close MongoDB connection. Called at app shutdown."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Return the active database instance. Must call connect_db() first."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db
