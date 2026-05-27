from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import EventType, Severity
from app.services.alert_service import AlertService, _cooldown
from app.services.telegram_notifier import format_telegram_alert


@pytest.mark.asyncio
async def test_high_cpu_event_sends_telegram_when_enabled():
    """HIGH_CPU events use the same Telegram notification channel as camera alerts."""
    db = MagicMock()
    service = AlertService(db)
    service._repo.create = AsyncMock(return_value={"id": "event-1"})
    _cooldown.clear()

    with (
        patch("app.services.alert_service.settings.telegram_enabled", True),
        patch("app.services.alert_service.send_telegram_alert", new=AsyncMock(return_value=True)) as sender,
        patch("app.services.alert_service.ws_manager.broadcast", new=AsyncMock()),
    ):
        await service.emit(
            camera_id="system",
            event_type=EventType.HIGH_CPU,
            severity=Severity.CRITICAL,
            message="HIGH CPU: 99.0%",
            metric_name="cpu_percent",
            metric_value=99.0,
            threshold=90.0,
        )

    sender.assert_awaited_once()
    assert sender.await_args.kwargs["project"] == "streaming-camera"
    assert sender.await_args.kwargs["alert_type"] == "CRITICAL / HIGH_CPU"
    assert sender.await_args.kwargs["source"] == "system"


@pytest.mark.asyncio
async def test_initial_camera_connected_event_is_not_sent_to_telegram():
    """Initial discovery is logged in the UI without sending startup noise."""
    service = AlertService(MagicMock())
    service._repo.create = AsyncMock(return_value={"id": "event-2"})
    _cooldown.clear()

    with (
        patch("app.services.alert_service.settings.telegram_enabled", True),
        patch("app.services.alert_service.send_telegram_alert", new=AsyncMock()) as sender,
        patch("app.services.alert_service.ws_manager.broadcast", new=AsyncMock()),
    ):
        await service.emit(
            camera_id="cam-1",
            event_type=EventType.CAMERA_CONNECTED,
            severity=Severity.INFO,
            message="Camera connected on application startup",
        )

    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_simulated_event_can_bypass_notification_cooldown():
    service = AlertService(MagicMock())
    service._repo.create = AsyncMock(return_value={"id": "event-3"})
    _cooldown.clear()

    with (
        patch("app.services.alert_service.settings.telegram_enabled", True),
        patch("app.services.alert_service.send_telegram_alert", new=AsyncMock(return_value=True)) as sender,
        patch("app.services.alert_service.ws_manager.broadcast", new=AsyncMock()),
    ):
        for _ in range(2):
            await service.emit(
                camera_id="system",
                event_type=EventType.HIGH_MEMORY,
                severity=Severity.CRITICAL,
                message="SIMULATED HIGH MEMORY",
                bypass_cooldown=True,
            )

    assert sender.await_count == 2


def test_telegram_alert_payload_has_shared_project_fields_and_escapes_html():
    message = format_telegram_alert(
        project="streaming-camera",
        alert_type="CRITICAL / HIGH_CPU",
        source="system",
        detail="CPU > 90% & urgent",
    )

    assert "<b>Project:</b> streaming-camera" in message
    assert "<b>Type:</b> CRITICAL / HIGH_CPU" in message
    assert "<b>Source:</b> system" in message
    assert "CPU &gt; 90% &amp; urgent" in message
