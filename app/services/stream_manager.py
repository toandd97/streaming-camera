"""
StreamManager — manages camera status by polling MediaMTX API.

Architecture (scalable to 80+ cameras):
    - No OpenCV workers — MediaMTX handles all RTSP/HLS transcoding
    - One background poller task polls MediaMTX /v3/paths/list every 5s
    - Status is derived from MediaMTX: path exists + has readers → CONNECTED
    - Emits alerts on connect/disconnect transitions
    - Emits a RECONNECT_TIMEOUT alert if a camera is not back online after
      RECONNECT_TIMEOUT_SECONDS (default 10s). Alert fires only once per
      disconnection cycle and resets when the camera reconnects.
    - Sim Off is a bounded failure drill: it automatically restores the
      actual MediaMTX state after SIMULATION_AUTO_RECONNECT_SECONDS (15s).

Why this scales:
    - 80 cameras = 1 polling task (not 80 threads)
    - No frame buffering in Python memory
    - No blocking OpenCV calls
    - CPU usage: ~0% per camera (MediaMTX handles decode)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.constants import CameraStatus, EventType, Severity
from app.models.runtime_status_model import RuntimeStatus

logger = logging.getLogger(__name__)

# Seconds without reconnection before a Telegram alert is sent.
RECONNECT_TIMEOUT_SECONDS = 10
# Seconds before a Sim Off drill automatically follows the real stream again.
SIMULATION_AUTO_RECONNECT_SECONDS = 15


class StreamManager:
    def __init__(self):
        # camera_id → RuntimeStatus (in-memory state)
        self._statuses: Dict[str, RuntimeStatus] = {}
        # camera_id → camera config dict (rtsp_url, display_fps, etc.)
        self._configs: Dict[str, dict] = {}
        # Background polling task
        self._poll_task: Optional[asyncio.Task] = None
        self._poll_interval: float = 5.0  # seconds between MediaMTX polls
        self.simulated_offline = set()
        self._simulation_reconnect_tasks: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_camera(self, camera: dict) -> None:
        """Register camera config and initialize status tracking."""
        camera_id = camera["id"]
        self._configs[camera_id] = camera
        if camera_id not in self._statuses:
            self._statuses[camera_id] = RuntimeStatus(
                camera_id=camera_id,
                display_fps=camera.get("display_fps", 5),
                status=CameraStatus.CONNECTING,
            )
        logger.info("StreamManager: registered camera %s (%s)", camera_id, camera.get("name"))

    async def stop_camera(self, camera_id: str) -> None:
        """Remove camera from tracking."""
        self._cancel_simulation_reconnect(camera_id)
        self.simulated_offline.discard(camera_id)
        self._configs.pop(camera_id, None)
        status = self._statuses.get(camera_id)
        if status:
            status.status = CameraStatus.STOPPED
            self._statuses.pop(camera_id, None)
        logger.info("StreamManager: unregistered camera %s", camera_id)

    async def restart_camera(self, camera: dict) -> None:
        """Re-register camera (e.g. when RTSP URL changes)."""
        camera_id = camera["id"]
        await self.stop_camera(camera_id)
        if camera.get("enabled", True):
            await self.start_camera(camera)

    async def stop_all(self) -> None:
        """Stop polling task and clear all state."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        for camera_id in list(self._simulation_reconnect_tasks):
            self._cancel_simulation_reconnect(camera_id)
        self.simulated_offline.clear()
        self._statuses.clear()
        self._configs.clear()
        logger.info("StreamManager: stopped all, polling task cancelled")

    async def load_on_startup(self, db: AsyncIOMotorDatabase) -> None:
        """Load all enabled cameras from MongoDB and start the polling loop."""
        from app.repositories.camera_repository import CameraRepository
        repo = CameraRepository(db)
        cameras = await repo.list_enabled()
        logger.info("StreamManager: loading %d enabled cameras on startup", len(cameras))
        for cam in cameras:
            await self.start_camera(cam)

        # Start the single background poller (replaces N OpenCV worker threads)
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="mediamtx-status-poller"
        )
        logger.info("StreamManager: MediaMTX poller started (interval=%ss)", self._poll_interval)

    # ------------------------------------------------------------------
    # MediaMTX Polling Loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Single background task that polls MediaMTX API for all cameras."""
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._poll_mediamtx()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("StreamManager: polling error: %s", e)

    async def _poll_mediamtx(self) -> None:
        """
        Poll MediaMTX /v3/paths/list and update all camera statuses.

        MediaMTX response structure:
            {"items": [{"name": "cam1", "readers": [...], ...}, ...]}

        A camera is CONNECTED if its rtsp_path appears in MediaMTX paths
        with at least 0 ready sources (path exists = stream is published).
        """
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.mediamtx_api_url}/v3/paths/list")
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("StreamManager: cannot reach MediaMTX API: %s", e)
            # Don't change status — keep last known state
            return

        # Build set of active (published) paths in MediaMTX
        active_paths: set[str] = set()
        for item in data.get("items", []):
            # A path is active if it has a source (someone is publishing to it)
            if item.get("ready", False) or item.get("readyTime") is not None:
                active_paths.add(item["name"])

        now = datetime.now(timezone.utc)

        for camera_id, config in list(self._configs.items()):
            status = self._statuses.get(camera_id)
            if not status:
                continue

            rtsp_path = _extract_rtsp_path(config.get("rtsp_url", ""))
            is_live = rtsp_path in active_paths and camera_id not in self.simulated_offline

            prev_status = status.status

            if is_live:
                if prev_status not in (CameraStatus.CONNECTED,):
                    # Transition → CONNECTED
                    recovered_after_alert = status.reconnect_timeout_alerted
                    status.status = CameraStatus.CONNECTED
                    status.last_connected_at = now
                    status.last_error = None
                    # Reset timeout alert flag so it fires again on next disconnection
                    status.reconnect_timeout_alerted = False
                    logger.info(
                        "StreamManager: camera %s CONNECTED (path=%s)",
                        camera_id, rtsp_path
                    )
                    if recovered_after_alert:
                        await self._emit_alert(
                            camera_id, config.get("name", camera_id),
                            EventType.CAMERA_RECONNECTED, Severity.INFO,
                            f"Camera {config.get('name', camera_id)} reconnected via MediaMTX",
                        )
                    elif prev_status == CameraStatus.CONNECTING:
                        await self._emit_alert(
                            camera_id, config.get("name", camera_id),
                            EventType.CAMERA_CONNECTED, Severity.INFO,
                            f"Camera {config.get('name', camera_id)} connected via MediaMTX",
                        )
                # Update uptime
                if status.last_connected_at:
                    delta = (now - status.last_connected_at).total_seconds()
                    status.uptime_seconds = delta
                status.last_frame_at = now  # MediaMTX is streaming = frames exist
                status.reconnect_count = max(status.reconnect_count, 0)

            else:
                if prev_status == CameraStatus.CONNECTED:
                    # Transition → DISCONNECTED
                    status.status = CameraStatus.DISCONNECTED
                    status.last_disconnected_at = now
                    status.last_error = "Stream not found in MediaMTX"
                    status.reconnect_timeout_alerted = False  # reset for new cycle
                    logger.warning(
                        "StreamManager: camera %s DISCONNECTED (path=%s not in MediaMTX)",
                        camera_id, rtsp_path
                    )
                    status.reconnect_count += 1
                elif prev_status == CameraStatus.CONNECTING:
                    status.status = CameraStatus.DISCONNECTED
                    status.last_disconnected_at = now
                    status.last_error = f"Stream path '{rtsp_path}' is not published in MediaMTX"
                    status.reconnect_timeout_alerted = False
                    logger.warning(
                        "StreamManager: camera %s not available (path=%s not in MediaMTX)",
                        camera_id, rtsp_path
                    )
                elif prev_status == CameraStatus.RECONNECTING:
                    # Check if camera has been unreachable for too long → one-shot alert
                    if (
                        not status.reconnect_timeout_alerted
                        and status.last_disconnected_at is not None
                        and (now - status.last_disconnected_at).total_seconds()
                            >= RECONNECT_TIMEOUT_SECONDS
                    ):
                        status.reconnect_timeout_alerted = True
                        elapsed = int((now - status.last_disconnected_at).total_seconds())
                        cam_name = config.get('name', camera_id)
                        logger.warning(
                            "StreamManager: camera %s still offline after %ds",
                            camera_id, elapsed
                        )
                        await self._emit_alert(
                            camera_id, cam_name,
                            EventType.CAMERA_DISCONNECTED, Severity.CRITICAL,
                            f"⚠️ Camera '{cam_name}' still offline after {elapsed}s — auto-reconnect failed"
                        )
                elif prev_status == CameraStatus.DISCONNECTED:
                    # Keep retrying (RECONNECTING state)
                    status.status = CameraStatus.RECONNECTING

    async def _emit_alert(
        self,
        camera_id: str,
        camera_name: str,
        event_type: EventType,
        severity: Severity,
        message: str,
    ) -> None:
        """Emit alert via AlertService (best-effort)."""
        try:
            from app.services.alert_service import get_alert_service
            alert_svc = get_alert_service()
            await alert_svc.emit(camera_id, event_type, severity, message)
        except Exception as e:
            logger.debug("StreamManager: alert emit failed: %s", e)

    # ------------------------------------------------------------------
    # Data access (called by CameraService and WebSocket routes)
    # ------------------------------------------------------------------

    def get_status(self, camera_id: str) -> Optional[dict]:
        status = self._statuses.get(camera_id)
        return status.to_dict() if status else None

    def get_all_statuses(self) -> Dict[str, dict]:
        """Return dict of camera_id → runtime status (for WebSocket snapshots)."""
        return {
            camera_id: status.to_dict()
            for camera_id, status in self._statuses.items()
        }

    def update_display_fps(self, camera_id: str, fps: int) -> None:
        """Hot-update display FPS (stored in status for API response)."""
        status = self._statuses.get(camera_id)
        if status:
            status.display_fps = fps
        config = self._configs.get(camera_id)
        if config:
            config["display_fps"] = fps

    async def simulate_disconnect(self, camera_id: str) -> None:
        """Force a temporary offline state, then automatically restore it."""
        self._cancel_simulation_reconnect(camera_id)
        self.simulated_offline.add(camera_id)
        status = self._statuses.get(camera_id)
        if status:
            status.simulated_offline = True
        self._simulation_reconnect_tasks[camera_id] = asyncio.create_task(
            self._auto_restore_simulation(camera_id),
            name=f"simulation-auto-reconnect-{camera_id}",
        )
        # Run a poll immediately to trigger transition/alerts/WebSocket broadcast
        await self._poll_mediamtx()

    async def simulate_reconnect(self, camera_id: str) -> None:
        """Restore camera to follow actual MediaMTX status."""
        self._cancel_simulation_reconnect(camera_id)
        self.simulated_offline.discard(camera_id)
        status = self._statuses.get(camera_id)
        if status:
            status.simulated_offline = False
        # Run a poll immediately to trigger transition/alerts/WebSocket broadcast
        await self._poll_mediamtx()

    async def _auto_restore_simulation(self, camera_id: str) -> None:
        try:
            await asyncio.sleep(SIMULATION_AUTO_RECONNECT_SECONDS)
            logger.info(
                "StreamManager: simulation for camera %s expired after %ss; restoring actual state",
                camera_id, SIMULATION_AUTO_RECONNECT_SECONDS,
            )
            await self.simulate_reconnect(camera_id)
        except asyncio.CancelledError:
            pass
        finally:
            task = self._simulation_reconnect_tasks.get(camera_id)
            if task is asyncio.current_task():
                self._simulation_reconnect_tasks.pop(camera_id, None)

    def _cancel_simulation_reconnect(self, camera_id: str) -> None:
        task = self._simulation_reconnect_tasks.pop(camera_id, None)
        if task and task is not asyncio.current_task():
            task.cancel()

    def get_hls_url(self, camera_id: str) -> Optional[str]:
        """
        Return the HLS URL for this camera.
        Browser-facing URL uses the public MediaMTX port (8888).
        """
        config = self._configs.get(camera_id)
        if not config:
            return None
        rtsp_path = _extract_rtsp_path(config.get("rtsp_url", ""))
        if not rtsp_path:
            return None
        return f"{settings.mediamtx_hls_base_url}/{rtsp_path}/index.m3u8"

    def get_latest_frame(self, camera_id: str):
        """Stub — no frames in memory. HLS serves video directly from MediaMTX."""
        return None

    @property
    def active_count(self) -> int:
        return sum(
            1 for s in self._statuses.values()
            if s.status == CameraStatus.CONNECTED
        )


def _extract_rtsp_path(rtsp_url: str) -> str:
    """
    Extract the path component from an RTSP URL.
    Examples:
        rtsp://mediamtx:8554/cam1       → "cam1"
        rtsp://192.168.1.1:8554/live/0  → "live/0"
        rtsp://host/path/sub            → "path/sub"
    """
    try:
        # Remove protocol
        without_proto = rtsp_url.split("://", 1)[-1]
        # Remove host:port
        path_part = without_proto.split("/", 1)[-1] if "/" in without_proto else ""
        # Strip trailing slash
        return path_part.strip("/")
    except Exception:
        return ""


# Singleton instance
stream_manager = StreamManager()
