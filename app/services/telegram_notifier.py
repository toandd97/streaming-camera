"""
Telegram Notifier — optional notification channel.

Sends alert messages to a Telegram chat via Bot API.
Must fail safely: any exception is logged but NOT propagated.
"""
import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str) -> bool:
    """
    Send a Telegram message. Returns True if sent successfully.

    Only active when TELEGRAM_ENABLED=true and credentials are configured.
    Never raises — all errors are caught and logged.
    """
    if not settings.telegram_enabled:
        return False
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram enabled but credentials not configured")
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Telegram notification sent successfully")
            return True
    except httpx.HTTPStatusError as e:
        logger.error("Telegram HTTP error: %s — %s", e.response.status_code, e.response.text)
    except Exception as e:
        logger.error("Telegram send failed: %s", e)

    return False
