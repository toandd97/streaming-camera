"""
CameraService — business logic for camera CRUD.

Coordinates:
    - CameraRepository (MongoDB)
    - StreamManager (runtime workers)
    - AlertService (events)
"""
import logging
from typing import Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.camera_repository import CameraRepository
from app.schemas.camera_schema import CameraCreate, CameraUpdate
from app.services.stream_manager import stream_manager

logger = logging.getLogger(__name__)


def _merge_with_runtime(camera_doc: dict) -> dict:
    """Merge MongoDB config with runtime status from StreamManager."""
    runtime = stream_manager.get_status(camera_doc["id"])
    if runtime:
        camera_doc.update({
            "status": runtime["status"],
            "actual_fps": runtime["actual_fps"],
            "latency_ms": runtime["latency_ms"],
            "frame_age_ms": runtime["frame_age_ms"],
            "uptime_seconds": runtime["uptime_seconds"],
            "reconnect_count": runtime["reconnect_count"],
            "last_frame_at": runtime["last_frame_at"],
            "last_connected_at": runtime["last_connected_at"],
            "last_disconnected_at": runtime["last_disconnected_at"],
            "last_error": runtime["last_error"],
        })
    return camera_doc


class CameraService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._repo = CameraRepository(db)

    async def create_camera(self, data: CameraCreate) -> dict:
        """Save config to MongoDB and start StreamWorker if enabled."""
        camera_dict = data.model_dump()
        saved = await self._repo.create(camera_dict)

        if data.enabled:
            await stream_manager.start_camera(saved)

        return _merge_with_runtime(saved)

    async def list_cameras(self) -> list[dict]:
        """List all cameras merged with runtime status."""
        cameras = await self._repo.list_all()
        return [_merge_with_runtime(c) for c in cameras]

    async def get_camera(self, camera_id: str) -> dict:
        """Get one camera with runtime status."""
        camera = await self._repo.get_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
        return _merge_with_runtime(camera)

    async def get_camera_status(self, camera_id: str) -> dict:
        """Get only runtime status for a camera."""
        camera = await self._repo.get_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
        runtime = stream_manager.get_status(camera_id)
        if not runtime:
            return {"camera_id": camera_id, "status": "STOPPED"}
        return runtime

    async def update_camera(self, camera_id: str, data: CameraUpdate) -> dict:
        """
        Update camera config.
        - If rtsp_url changed: restart StreamWorker with new URL
        - If only name/display_fps changed: update without restarting RTSP connection
        """
        existing = await self._repo.get_by_id(camera_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        updated = await self._repo.update(camera_id, update_dict)
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Update failed")

        rtsp_changed = data.rtsp_url and data.rtsp_url != existing["rtsp_url"]
        enabled_changed = data.enabled is not None and data.enabled != existing["enabled"]

        if rtsp_changed or enabled_changed:
            # Restart worker
            await stream_manager.restart_camera(updated)
        elif data.display_fps is not None:
            # Hot-update display FPS without restart
            stream_manager.update_display_fps(camera_id, data.display_fps)

        return _merge_with_runtime(updated)

    async def update_display_fps(self, camera_id: str, display_fps: int) -> dict:
        """PATCH display FPS — hot-apply without restarting RTSP connection."""
        camera = await self._repo.get_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

        await self._repo.update(camera_id, {"display_fps": display_fps})
        stream_manager.update_display_fps(camera_id, display_fps)

        updated = await self._repo.get_by_id(camera_id)
        return _merge_with_runtime(updated)

    async def delete_camera(self, camera_id: str) -> dict:
        """Stop worker, delete from MongoDB."""
        camera = await self._repo.get_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

        await stream_manager.stop_camera(camera_id)
        await self._repo.delete(camera_id)
        return {"message": f"Camera {camera_id} deleted successfully"}
