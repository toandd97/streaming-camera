"""
Tests for stream status logic.

These test StreamWorker state transitions without needing real RTSP.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

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


def test_stream_worker_initial_status():
    """StreamWorker should initialize with CREATED status."""
    from app.services.stream_worker import StreamWorker

    worker = StreamWorker("cam-1", "Test Camera", "rtsp://test/cam1", display_fps=5)
    assert worker.status.status == CameraStatus.CREATED
    assert worker.status.reconnect_count == 0
    assert worker.get_latest_frame() is None


def test_stream_worker_update_display_fps():
    """update_display_fps should update the runtime status."""
    from app.services.stream_worker import StreamWorker

    worker = StreamWorker("cam-1", "Test Camera", "rtsp://test/cam1", display_fps=5)
    worker.update_display_fps(10)
    assert worker.status.display_fps == 10


def test_format_uptime():
    """format_uptime should produce human-readable strings."""
    from app.utils.time_utils import format_uptime

    assert format_uptime(0) == "0s"
    assert format_uptime(45) == "45s"
    assert format_uptime(90) == "1m 30s"
    assert format_uptime(3661) == "1h 1m 1s"


def test_image_utils_blank_frame():
    """get_blank_frame should return valid JPEG bytes."""
    from app.utils.image_utils import get_blank_frame

    frame = get_blank_frame()
    assert isinstance(frame, bytes)
    assert len(frame) > 0
    # JPEG magic bytes
    assert frame[:2] == b'\xff\xd8'
