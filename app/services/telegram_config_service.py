"""Persistent runtime Telegram notification configuration."""
import logging

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.schemas.metrics_schema import TelegramConfigResponse, TelegramConfigUpdate
from app.services.telegram_notifier import format_telegram_alert, send_telegram_message_to

logger = logging.getLogger(__name__)
_CONFIG_KEY = "telegram"


def get_telegram_configuration() -> TelegramConfigResponse:
    return TelegramConfigResponse(
        enabled=settings.telegram_enabled,
        token_configured=bool(settings.telegram_bot_token),
        chat_id=settings.telegram_chat_id,
        project=settings.alert_project_name,
    )


async def load_telegram_configuration(db: AsyncIOMotorDatabase) -> None:
    """Load dashboard-saved credentials over environment defaults."""
    stored = await db.app_settings.find_one({"key": _CONFIG_KEY})
    if not stored:
        settings.telegram_enabled = False
        return

    settings.telegram_enabled = bool(stored.get("enabled") and stored.get("verified"))
    settings.telegram_bot_token = stored.get("bot_token") or settings.telegram_bot_token
    settings.telegram_chat_id = stored.get("chat_id") or settings.telegram_chat_id
    logger.info("Loaded persisted Telegram configuration (enabled=%s)", settings.telegram_enabled)


async def update_telegram_configuration(
    db: AsyncIOMotorDatabase,
    data: TelegramConfigUpdate,
) -> TelegramConfigResponse:
    token = (data.bot_token or "").strip() or settings.telegram_bot_token
    chat_id = data.chat_id.strip()
    if not token or not chat_id:
        raise HTTPException(
            status_code=400,
            detail="Bot token and chat ID are required to test Telegram alerts",
        )

    verified = await send_telegram_message_to(
        bot_token=token,
        chat_id=chat_id,
        message=format_telegram_alert(
            project=settings.alert_project_name,
            alert_type="TEST / TELEGRAM_CONFIGURATION",
            source="dashboard",
            detail="Telegram notifications were verified successfully.",
        ),
    )
    if not verified:
        raise HTTPException(
            status_code=400,
            detail="Telegram test message failed. Check bot token and chat ID.",
        )

    settings.telegram_enabled = True
    settings.telegram_bot_token = token
    settings.telegram_chat_id = chat_id
    await db.app_settings.update_one(
        {"key": _CONFIG_KEY},
        {
            "$set": {
                "key": _CONFIG_KEY,
                "enabled": True,
                "verified": True,
                "bot_token": token,
                "chat_id": chat_id,
            }
        },
        upsert=True,
    )
    logger.info("Verified and enabled persisted Telegram configuration")
    return get_telegram_configuration()
