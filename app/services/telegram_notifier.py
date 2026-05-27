"""
Telegram Notifier — optional notification channel.

Sends alert messages to a Telegram chat via Bot API.
Must fail safely: any exception is logged but NOT propagated.
"""
import logging
from html import escape

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def format_telegram_alert(
    *,
    project: str,
    alert_type: str,
    detail: str,
    source: str,
) -> str:
    """Create a common Telegram alert format that identifies the source app."""
    return (
        "<b>ALERT</b>\n"
        f"<b>Project:</b> {escape(project)}\n"
        f"<b>Type:</b> {escape(alert_type)}\n"
        f"<b>Source:</b> {escape(source)}\n"
        f"<b>Detail:</b> {escape(detail)}"
    )


async def send_telegram_alert(
    *,
    project: str,
    alert_type: str,
    detail: str,
    source: str,
) -> bool:
    """Send a structured alert shared by camera and system notifications."""
    return await send_telegram_message(
        format_telegram_alert(
            project=project,
            alert_type=alert_type,
            detail=detail,
            source=source,
        )
    )


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

    return await send_telegram_message_to(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        message=message,
    )


async def send_telegram_message_to(*, bot_token: str, chat_id: str, message: str) -> bool:
    """Send using supplied credentials, including before alerts are enabled."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
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
