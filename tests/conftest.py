"""
pytest configuration and shared fixtures.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    db = MagicMock()
    db.cameras = MagicMock()
    db.stream_events = MagicMock()
    return db


@pytest.fixture
def mock_stream_manager():
    """Mock StreamManager with no active workers."""
    manager = MagicMock()
    manager.get_status.return_value = {
        "camera_id": "test-id",
        "status": "CONNECTING",
        "actual_fps": 0.0,
        "display_fps": 5,
        "latency_ms": 0.0,
        "frame_age_ms": 0.0,
        "uptime_seconds": 0.0,
        "reconnect_count": 0,
        "last_frame_at": None,
        "last_connected_at": None,
        "last_disconnected_at": None,
        "last_error": None,
    }
    manager.get_all_statuses.return_value = {}
    manager.active_count = 0
    manager.start_camera = AsyncMock()
    manager.stop_camera = AsyncMock()
    manager.restart_camera = AsyncMock()
    manager.update_display_fps = MagicMock()
    return manager
