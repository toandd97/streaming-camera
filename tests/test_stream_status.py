"""
Tests for stream status logic.

These test StreamWorker state transitions without needing real RTSP.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta, timezone

from app.core.constants import CameraStatus
from app.models.runtime_status_model import RuntimeStatus


def test_runtime_status_initial_state():
    """RuntimeStatus should start as CREATED with zeroed metrics."""
    status = RuntimeStatus(camera_id="cam-1")
    assert status.status == CameraStatus.CREATED
    assert status.actual_fps == 0.0
    assert status.reconnect_count == 0
    assert status.last_frame_at is None


def test_runtime_status_to_dict():
    """to_dict() should serialize all fields correctly."""
    status = RuntimeStatus(
        camera_id="cam-1",
        status=CameraStatus.CONNECTED,
        actual_fps=24.5,
        reconnect_count=2,
    )
    d = status.to_dict()
    assert d["camera_id"] == "cam-1"
    assert d["status"] == "CONNECTED"
    assert d["actual_fps"] == 24.5
    assert d["reconnect_count"] == 2


def test_fps_calculator_sliding_window():
    """SlidingWindowFPS should correctly calculate FPS."""
    import time
    from app.utils.fps_calculator import SlidingWindowFPS

    fps_calc = SlidingWindowFPS(window_size=10)

    # Simulate 10 frames at ~10 FPS (0.1s apart)
    for _ in range(10):
        fps_calc.tick()
        time.sleep(0.05)

    fps = fps_calc.get_fps()
    # Should be roughly 20 FPS (0.05s interval)
    assert fps > 10.0, f"Expected FPS > 10, got {fps}"

    # After reset, FPS should be 0
    fps_calc.reset()
    assert fps_calc.get_fps() == 0.0


def test_fps_calculator_insufficient_frames():
    """FPS should be 0 with fewer than 2 frames."""
    from app.utils.fps_calculator import SlidingWindowFPS

    fps_calc = SlidingWindowFPS()
    assert fps_calc.get_fps() == 0.0
    fps_calc.tick()
    assert fps_calc.get_fps() == 0.0


def test_format_uptime():
    """format_uptime should produce human-readable strings."""
    from app.utils.time_utils import format_uptime

    assert format_uptime(0) == "0s"
    assert format_uptime(45) == "45s"
    assert format_uptime(90) == "1m 30s"
    assert format_uptime(3661) == "1h 1m 1s"


@pytest.mark.asyncio
async def test_stream_manager_simulation():
    """StreamManager should allow simulating offline state and reconnecting."""
    from app.services.stream_manager import StreamManager
    from app.core.constants import CameraStatus

    mgr = StreamManager()
    camera = {
        "id": "test-cam-123",
        "name": "Simulated Camera",
        "rtsp_url": "rtsp://localhost:8554/test-cam",
        "resolution": "640x360",
        "target_fps": 10,
        "display_fps": 5,
        "enabled": True,
    }

    await mgr.start_camera(camera)

    # Initially status is CONNECTING
    assert mgr._statuses["test-cam-123"].status == CameraStatus.CONNECTING
    assert not mgr._statuses["test-cam-123"].simulated_offline

    # Simulate disconnect
    with patch.object(mgr, "_poll_mediamtx", AsyncMock()) as mock_poll:
        await mgr.simulate_disconnect("test-cam-123")
        assert mgr._statuses["test-cam-123"].simulated_offline
        assert "test-cam-123" in mgr.simulated_offline
        mock_poll.assert_called_once()

    # Simulate reconnect
    with patch.object(mgr, "_poll_mediamtx", AsyncMock()) as mock_poll:
        await mgr.simulate_reconnect("test-cam-123")
        assert not mgr._statuses["test-cam-123"].simulated_offline
        assert "test-cam-123" not in mgr.simulated_offline
        mock_poll.assert_called_once()

    await mgr.stop_all()


@pytest.mark.asyncio
async def test_stream_manager_simulation_automatically_reconnects(monkeypatch):
    """A Sim Off drill should stop forcing the stream offline after its timeout."""
    from app.services import stream_manager as stream_manager_module
    from app.services.stream_manager import StreamManager

    monkeypatch.setattr(stream_manager_module, "SIMULATION_AUTO_RECONNECT_SECONDS", 0)
    mgr = StreamManager()
    camera_id = "test-cam-auto"
    await mgr.start_camera({
        "id": camera_id,
        "name": "Automatic Restore Camera",
        "rtsp_url": "rtsp://localhost:8554/test-cam-auto",
        "display_fps": 5,
    })

    with patch.object(mgr, "_poll_mediamtx", AsyncMock()) as mock_poll:
        await mgr.simulate_disconnect(camera_id)
        auto_restore_task = mgr._simulation_reconnect_tasks[camera_id]
        await auto_restore_task

        assert not mgr._statuses[camera_id].simulated_offline
        assert camera_id not in mgr.simulated_offline
        assert mock_poll.await_count == 2

    await mgr.stop_all()


@pytest.mark.asyncio
async def test_stream_manager_manual_reconnect_cancels_automatic_reconnect():
    """Pressing Sim On should prevent a later duplicate automatic restore."""
    from app.services.stream_manager import StreamManager

    mgr = StreamManager()
    camera_id = "test-cam-manual"
    await mgr.start_camera({
        "id": camera_id,
        "name": "Manual Restore Camera",
        "rtsp_url": "rtsp://localhost:8554/test-cam-manual",
        "display_fps": 5,
    })

    with patch.object(mgr, "_poll_mediamtx", AsyncMock()) as mock_poll:
        await mgr.simulate_disconnect(camera_id)
        task = mgr._simulation_reconnect_tasks[camera_id]
        await mgr.simulate_reconnect(camera_id)
        await asyncio.sleep(0)

        assert task.cancelled()
        assert camera_id not in mgr._simulation_reconnect_tasks
        assert mock_poll.await_count == 2

    await mgr.stop_all()


@pytest.mark.asyncio
async def test_stream_loss_only_emits_alert_after_reconnect_timeout():
    """A transient disconnect must not notify until it remains offline for 10s."""
    from app.services.stream_manager import StreamManager

    mgr = StreamManager()
    camera_id = "test-cam-timeout"
    await mgr.start_camera({
        "id": camera_id,
        "name": "Timeout Camera",
        "rtsp_url": "rtsp://localhost:8554/test-cam-timeout",
        "display_fps": 5,
    })
    status = mgr._statuses[camera_id]
    status.status = CameraStatus.CONNECTED

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"items": []}
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(return_value=response)

    with (
        patch("app.services.stream_manager.httpx.AsyncClient", return_value=client),
        patch.object(mgr, "_emit_alert", AsyncMock()) as emit,
    ):
        await mgr._poll_mediamtx()
        emit.assert_not_awaited()

        status.status = CameraStatus.RECONNECTING
        status.last_disconnected_at = datetime.now(timezone.utc) - timedelta(seconds=11)
        await mgr._poll_mediamtx()

    emit.assert_awaited_once()
    assert emit.await_args.args[2].value == "CAMERA_DISCONNECTED"
    await mgr.stop_all()


@pytest.mark.asyncio
async def test_initial_live_stream_creates_connected_event():
    """Discovering an online camera emits its existing connection event."""
    from app.services.stream_manager import StreamManager

    mgr = StreamManager()
    camera_id = "test-cam-startup"
    await mgr.start_camera({
        "id": camera_id,
        "name": "Online Camera",
        "rtsp_url": "rtsp://localhost:8554/test-cam-startup",
        "display_fps": 5,
    })

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"items": [{"name": "test-cam-startup", "ready": True}]}
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(return_value=response)

    with (
        patch("app.services.stream_manager.httpx.AsyncClient", return_value=client),
        patch.object(mgr, "_emit_alert", AsyncMock()) as emit,
    ):
        await mgr._poll_mediamtx()

    assert mgr._statuses[camera_id].status == CameraStatus.CONNECTED
    emit.assert_awaited_once()
    assert emit.await_args.args[2].value == "CAMERA_CONNECTED"
    await mgr.stop_all()
