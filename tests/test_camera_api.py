"""
Tests for camera CRUD API.

These tests mock MongoDB and StreamManager to run without Docker.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


FAKE_CAMERA_DOC = {
    "id": "665f000000000000000000a1",
    "name": "Test Cam",
    "rtsp_url": "rtsp://mediamtx:8554/cam1",
    "resolution": "640x360",
    "target_fps": 10,
    "display_fps": 5,
    "enabled": True,
    "description": None,
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
}

FAKE_RUNTIME = {
    "camera_id": "665f000000000000000000a1",
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


@pytest.mark.asyncio
async def test_create_camera_success():
    """POST /cameras should save config and start worker."""
    from app.services.camera_service import CameraService
    from app.schemas.camera_schema import CameraCreate

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value=FAKE_CAMERA_DOC.copy())

    with patch("app.services.camera_service.CameraRepository", return_value=mock_repo):
        with patch("app.services.camera_service.stream_manager") as mock_sm:
            mock_sm.start_camera = AsyncMock()
            mock_sm.get_status = MagicMock(return_value=FAKE_RUNTIME)

            svc = CameraService(MagicMock())
            svc._repo = mock_repo

            data = CameraCreate(
                name="Test Cam",
                rtsp_url="rtsp://mediamtx:8554/cam1",
                resolution="640x360",
                target_fps=10,
                display_fps=5,
                enabled=True,
            )

            result = await svc.create_camera(data)

            mock_repo.create.assert_called_once()
            mock_sm.start_camera.assert_called_once()
            assert result["name"] == "Test Cam"
            assert result["status"] == "CONNECTING"


@pytest.mark.asyncio
async def test_list_cameras_merges_runtime_status():
    """GET /cameras should return config merged with runtime status."""
    from app.services.camera_service import CameraService

    mock_repo = MagicMock()
    mock_repo.list_all = AsyncMock(return_value=[FAKE_CAMERA_DOC.copy()])

    with patch("app.services.camera_service.stream_manager") as mock_sm:
        mock_sm.get_status = MagicMock(return_value=FAKE_RUNTIME)

        svc = CameraService(MagicMock())
        svc._repo = mock_repo

        cameras = await svc.list_cameras()

        assert len(cameras) == 1
        cam = cameras[0]
        assert "status" in cam
        assert "actual_fps" in cam
        assert "reconnect_count" in cam


@pytest.mark.asyncio
async def test_delete_camera_stops_worker():
    """DELETE /cameras/{id} should stop worker and delete from DB."""
    from app.services.camera_service import CameraService

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=FAKE_CAMERA_DOC.copy())
    mock_repo.delete = AsyncMock(return_value=True)

    with patch("app.services.camera_service.stream_manager") as mock_sm:
        mock_sm.stop_camera = AsyncMock()

        svc = CameraService(MagicMock())
        svc._repo = mock_repo

        result = await svc.delete_camera("665f000000000000000000a1")

        mock_sm.stop_camera.assert_called_once_with("665f000000000000000000a1")
        mock_repo.delete.assert_called_once()
        assert "deleted" in result["message"]


@pytest.mark.asyncio
async def test_update_display_fps_no_restart():
    """PATCH display-fps should not restart the RTSP worker."""
    from app.services.camera_service import CameraService

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=FAKE_CAMERA_DOC.copy())
    mock_repo.update = AsyncMock(return_value=None)

    updated = {**FAKE_CAMERA_DOC, "display_fps": 10}
    mock_repo.get_by_id.side_effect = [FAKE_CAMERA_DOC.copy(), updated]

    with patch("app.services.camera_service.stream_manager") as mock_sm:
        mock_sm.update_display_fps = MagicMock()
        mock_sm.restart_camera = AsyncMock()
        mock_sm.get_status = MagicMock(return_value={**FAKE_RUNTIME, "display_fps": 10})

        svc = CameraService(MagicMock())
        svc._repo = mock_repo

        result = await svc.update_display_fps("665f000000000000000000a1", 10)

        # Should NOT restart worker
        mock_sm.restart_camera.assert_not_called()
        # Should update display_fps in memory
        mock_sm.update_display_fps.assert_called_once_with("665f000000000000000000a1", 10)


@pytest.mark.asyncio
async def test_get_camera_not_found():
    """GET /cameras/{id} with invalid ID should raise 404."""
    from app.services.camera_service import CameraService
    from fastapi import HTTPException

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)

    svc = CameraService(MagicMock())
    svc._repo = mock_repo

    with pytest.raises(HTTPException) as exc_info:
        await svc.get_camera("nonexistent-id")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_invalid_rtsp_url_format():
    """Camera with invalid display_fps should raise validation error."""
    from app.schemas.camera_schema import CameraCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CameraCreate(
            name="Test",
            rtsp_url="rtsp://host/path",
            display_fps=99,  # Not in ALLOWED_DISPLAY_FPS
        )
