"""
Alert Service — receives events, persists to MongoDB, sends Telegram alerts with cooldown.

Responsibilities:
    - Save stream events to MongoDB via StreamEventRepository
    - Apply per-camera/per-event-type cooldown to avoid alert spam
    - Optionally send Telegram notifications
    - Broadcast events through WebSocketManager
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.constants import EventType, Severity
from app.core.config import settings
from app.repositories.stream_event_repository import StreamEventRepository
from app.services.telegram_notifier import send_telegram_message
from app.services.websocket_manager import ws_manager
from app.core.constants import WS_STREAM_EVENT

logger = logging.getLogger(__name__)

# Cooldown state: (camera_id, event_type) -> last_notified timestamp
_cooldown: Dict[Tuple[str, str], datetime] = {}


class AlertService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._repo = StreamEventRepository(db)

    async def emit(
        self,
        camera_id: str,
        event_type: EventType,
        severity: Severity,
        message: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> None:
        """
        Process an event:
        1. Save to MongoDB
        2. Check cooldown
        3. Send Telegram if enabled and cooldown passed
        4. Broadcast via WebSocket
        """
        now = datetime.now(timezone.utc)

        # 1. Save to MongoDB
        event_data = {
            "camera_id": camera_id,
            "event_type": event_type.value,
            "severity": severity.value,
            "message": message,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "threshold": threshold,
            "notified": False,
            "created_at": now,
        }

        try:
            saved = await self._repo.create(event_data)
        except Exception as e:
            logger.error("Failed to save stream event: %s", e)
            saved = event_data

        logger.info("[EVENT] %s | %s | %s", severity.value, event_type.value, message)

        # 2. Check cooldown
        cooldown_key = (camera_id, event_type.value)
        last_notified = _cooldown.get(cooldown_key)
        cooldown_passed = (
            last_notified is None
            or (now - last_notified).total_seconds() > settings.alert_cooldown_seconds
        )

        # 3. Send Telegram if enabled
        notified = False
        if cooldown_passed and settings.telegram_enabled:
            tg_message = (
                f"🚨 <b>{severity.value}</b> | {event_type.value}\n"
                f"Camera: {camera_id}\n"
                f"Message: {message}"
            )
            notified = await send_telegram_message(tg_message)
            if notified:
                _cooldown[cooldown_key] = now
                # Update notified flag in DB
                try:
                    if "id" in saved:
                        from app.db.mongodb import get_database
                        db = get_database()
                        from bson import ObjectId
                        await db.stream_events.update_one(
                            {"_id": ObjectId(saved["id"])},
                            {"$set": {"notified": True}}
                        )
                except Exception as e:
                    logger.error("Failed to update notified flag: %s", e)

        # 4. Broadcast to WebSocket clients
        await ws_manager.broadcast({
            "type": WS_STREAM_EVENT,
            "data": {
                "id": saved.get("id", ""),
                "camera_id": camera_id,
                "event_type": event_type.value,
                "severity": severity.value,
                "message": message,
                "created_at": now.isoformat(),
                "notified": notified,
            }
        })


# Singleton — will be initialized in main.py with db instance
_alert_service: Optional[AlertService] = None


def init_alert_service(db: AsyncIOMotorDatabase) -> AlertService:
    global _alert_service
    _alert_service = AlertService(db)
    return _alert_service


def get_alert_service() -> AlertService:
    if _alert_service is None:
        raise RuntimeError("AlertService not initialized")
    return _alert_service
