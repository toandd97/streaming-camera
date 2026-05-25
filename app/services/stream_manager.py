"""
StreamManager — manages all StreamWorkers.

Responsibilities:
    - Keep dict: camera_id -> StreamWorker
    - Start/stop/restart workers
    - Expose latest frames and aggregated runtime statuses
    - Load enabled cameras from MongoDB on backend startup
"""
import logging
from typing import Dict, Optional
import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.stream_worker import StreamWorker

logger = logging.getLogger(__name__)


class StreamManager:
    def __init__(self):
        self._workers: Dict[str, StreamWorker] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_camera(self, camera: dict) -> None:
        """Create and start a StreamWorker for the given camera config."""
        camera_id = camera["id"]
        if camera_id in self._workers:
            logger.warning("Worker already exists for camera %s, stopping first", camera_id)
            await self.stop_camera(camera_id)

        worker = StreamWorker(
            camera_id=camera_id,
            camera_name=camera["name"],
            rtsp_url=camera["rtsp_url"],
            display_fps=camera.get("display_fps", 5),
        )
        self._workers[camera_id] = worker
        worker.start()
        logger.info("StreamManager: started worker for camera %s", camera_id)

    async def stop_camera(self, camera_id: str) -> None:
        """Stop and remove a StreamWorker."""
        worker = self._workers.pop(camera_id, None)
        if worker:
            await worker.stop()
            logger.info("StreamManager: stopped worker for camera %s", camera_id)

    async def restart_camera(self, camera: dict) -> None:
        """Stop existing worker and start a new one (e.g. when RTSP URL changes)."""
        camera_id = camera["id"]
        await self.stop_camera(camera_id)
        if camera.get("enabled", True):
            await self.start_camera(camera)

    async def stop_all(self) -> None:
        """Stop all workers. Called on backend shutdown."""
        ids = list(self._workers.keys())
        for camera_id in ids:
            await self.stop_camera(camera_id)
        logger.info("StreamManager: all workers stopped")

    async def load_on_startup(self, db: AsyncIOMotorDatabase) -> None:
        """Load all enabled cameras from MongoDB and start workers."""
        from app.repositories.camera_repository import CameraRepository
        repo = CameraRepository(db)
        cameras = await repo.list_enabled()
        logger.info("StreamManager: loading %d enabled cameras on startup", len(cameras))
        for cam in cameras:
            await self.start_camera(cam)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_latest_frame(self, camera_id: str) -> Optional[np.ndarray]:
        worker = self._workers.get(camera_id)
        return worker.get_latest_frame() if worker else None

    def get_status(self, camera_id: str) -> Optional[dict]:
        worker = self._workers.get(camera_id)
        return worker.status.to_dict() if worker else None

    def get_all_statuses(self) -> Dict[str, dict]:
        """Return dict of camera_id -> runtime status for batch API."""
        return {
            camera_id: worker.status.to_dict()
            for camera_id, worker in self._workers.items()
        }

    def update_display_fps(self, camera_id: str, fps: int) -> None:
        """Apply new display FPS to worker immediately — no RTSP restart needed."""
        worker = self._workers.get(camera_id)
        if worker:
            worker.update_display_fps(fps)

    @property
    def active_count(self) -> int:
        return len(self._workers)


# Singleton instance
stream_manager = StreamManager()
