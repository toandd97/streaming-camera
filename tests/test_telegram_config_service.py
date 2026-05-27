from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.metrics_schema import TelegramConfigUpdate
from app.services.telegram_config_service import (
    get_telegram_configuration,
    load_telegram_configuration,
    update_telegram_configuration,
)


@pytest.mark.asyncio
async def test_update_telegram_configuration_persists_secret_without_exposing_it():
    db = MagicMock()
    db.app_settings.update_one = AsyncMock()

    with (
        patch("app.services.telegram_config_service.settings.telegram_enabled", False),
        patch("app.services.telegram_config_service.settings.telegram_bot_token", ""),
        patch("app.services.telegram_config_service.settings.telegram_chat_id", ""),
        patch(
            "app.services.telegram_config_service.send_telegram_message_to",
            new=AsyncMock(return_value=True),
        ) as sender,
    ):
        result = await update_telegram_configuration(
            db,
            TelegramConfigUpdate(bot_token="new-token", chat_id="12345"),
        )

    sender.assert_awaited_once()
    assert result.enabled is True
    assert result.token_configured is True
    assert result.chat_id == "12345"
    payload = db.app_settings.update_one.await_args.args[1]["$set"]
    assert payload["bot_token"] == "new-token"


@pytest.mark.asyncio
async def test_load_telegram_configuration_overrides_environment_defaults():
    db = MagicMock()
    db.app_settings.find_one = AsyncMock(return_value={
        "enabled": True,
        "verified": True,
        "bot_token": "saved-token",
        "chat_id": "saved-chat",
    })

    with (
        patch("app.services.telegram_config_service.settings.telegram_enabled", False),
        patch("app.services.telegram_config_service.settings.telegram_bot_token", "env-token"),
        patch("app.services.telegram_config_service.settings.telegram_chat_id", "env-chat"),
    ):
        await load_telegram_configuration(db)
        result = get_telegram_configuration()

    assert result.enabled is True
    assert result.token_configured is True
    assert result.chat_id == "saved-chat"


@pytest.mark.asyncio
async def test_unverified_saved_configuration_loads_disabled():
    db = MagicMock()
    db.app_settings.find_one = AsyncMock(return_value={
        "enabled": True,
        "bot_token": "unverified-token",
        "chat_id": "unverified-chat",
    })

    with (
        patch("app.services.telegram_config_service.settings.telegram_enabled", True),
        patch("app.services.telegram_config_service.settings.telegram_bot_token", ""),
        patch("app.services.telegram_config_service.settings.telegram_chat_id", ""),
    ):
        await load_telegram_configuration(db)
        result = get_telegram_configuration()

    assert result.enabled is False


@pytest.mark.asyncio
async def test_failed_test_message_does_not_enable_or_persist_configuration():
    db = MagicMock()
    db.app_settings.update_one = AsyncMock()

    with (
        patch("app.services.telegram_config_service.settings.telegram_enabled", False),
        patch("app.services.telegram_config_service.settings.telegram_bot_token", ""),
        patch(
            "app.services.telegram_config_service.send_telegram_message_to",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await update_telegram_configuration(
                db,
                TelegramConfigUpdate(bot_token="wrong-token", chat_id="12345"),
            )

    assert "test message failed" in str(exc.value.detail).lower()
    db.app_settings.update_one.assert_not_awaited()
