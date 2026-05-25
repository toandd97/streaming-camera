"""
StreamWorker — one worker per camera.

Runs in a dedicated asyncio task. Uses run_in_executor for blocking OpenCV calls.

State machine:
    CONNECTING → CONNECTED (frames received)
    CONNECTED  → DISCONNECTED (no frame for NO_FRAME_TIMEOUT_SECONDS)
    DISCONNECTED → RECONNECTING
    RECONNECTING → CONNECTED or RECONNECTING (retry loop)
    Any state → STOPPED (explicit stop)
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.constants import CameraStatus, EventType, Severity
from app.models.runtime_status_model import RuntimeStatus
from app.utils.fps_calculator import SlidingWindowFPS

logger = logging.getLogger(__name__)


class StreamWorker:
    def __init__(self, camera_id: str, camera_name: str, rtsp_url: str, display_fps: int):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url

        self.status = RuntimeStatus(camera_id=camera_id, display_fps=display_fps)
        self._latest_frame: Optional[np.ndarray] = None
        self._fps_calc = SlidingWindowFPS(window_size=30)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._loop_start: Optional[float] = None
        self._connected_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Schedule the worker task on the current event loop."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name=f"worker-{self.camera_id}")
        logger.info("StreamWorker started for camera %s (%s)", self.camera_id, self.camera_name)

    async def stop(self) -> None:
        """Signal the worker to stop and wait for it to finish."""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.status.status = CameraStatus.STOPPED
        self._latest_frame = None
        logger.info("StreamWorker stopped for camera %s", self.camera_id)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        return self._latest_frame

    def update_display_fps(self, fps: int) -> None:
        self.status.display_fps = fps

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Main worker loop: connect → read frames → handle timeout → reconnect."""
        loop = asyncio.get_event_loop()
        alert_service = None

        # Import here to avoid circular imports
        try:
            from app.services.alert_service import get_alert_service
            alert_service = get_alert_service()
        except Exception:
            pass  # AlertService may not be ready in tests

        while not self._stop_event.is_set():
            # --- Connect ---
            self.status.status = CameraStatus.CONNECTING
            logger.info("[%s] Connecting to RTSP: %s", self.camera_name, self.rtsp_url)

            cap = await loop.run_in_executor(None, self._open_capture)

            if cap is None or not cap.isOpened():
                logger.warning("[%s] Failed to open RTSP stream, retrying in %ss",
                               self.camera_name, settings.reconnect_interval_seconds)
                self.status.status = CameraStatus.RECONNECTING
                self.status.reconnect_count += 1
                self.status.last_error = "Could not open RTSP stream"
                await asyncio.sleep(settings.reconnect_interval_seconds)
                continue

            # --- Connected ---
            now = datetime.now(timezone.utc)
            self.status.status = CameraStatus.CONNECTED
            self.status.last_connected_at = now
            self.status.last_error = None
            self._connected_at = time.monotonic()
            self._fps_calc.reset()
            logger.info("[%s] CONNECTED to RTSP stream", self.camera_name)

            if alert_service:
                try:
                    await alert_service.emit(
                        self.camera_id, EventType.CAMERA_CONNECTED, Severity.INFO,
                        f"Camera {self.camera_name} connected successfully"
                    )
                except Exception:
                    pass

            # --- Frame reading loop ---
            disconnected = await self._read_frames(cap, loop, alert_service)

            # Release capture
            await loop.run_in_executor(None, cap.release)

            if self._stop_event.is_set():
                break

            if disconnected:
                # Trigger reconnect
                now = datetime.now(timezone.utc)
                self.status.status = CameraStatus.RECONNECTING
                self.status.reconnect_count += 1
                self.status.last_disconnected_at = now
                self.status.last_error = f"No frame received for {settings.no_frame_timeout_seconds}s"

                if alert_service:
                    try:
                        await alert_service.emit(
                            self.camera_id, EventType.CAMERA_DISCONNECTED, Severity.CRITICAL,
                            f"Camera {self.camera_name} disconnected: no frame for {settings.no_frame_timeout_seconds}s",
                            metric_name="no_frame_duration_seconds",
                            metric_value=settings.no_frame_timeout_seconds,
                            threshold=settings.no_frame_timeout_seconds,
                        )
                    except Exception:
                        pass

                logger.warning("[%s] Disconnected. Reconnecting in %ss...",
                               self.camera_name, settings.reconnect_interval_seconds)
                await asyncio.sleep(settings.reconnect_interval_seconds)

        self.status.status = CameraStatus.STOPPED

    async def _read_frames(self, cap, loop, alert_service) -> bool:
        """
        Read frames continuously.
        Returns True if disconnected due to timeout, False if stopped normally.
        """
        last_frame_time = time.monotonic()
        low_fps_start: Optional[float] = None
        last_fps_alert = 0.0

        while not self._stop_event.is_set():
            # Read one frame in executor (blocking)
            ret, frame = await loop.run_in_executor(None, cap.read)

            now_mono = time.monotonic()

            if ret and frame is not None:
                self._latest_frame = frame
                self._fps_calc.tick()
                last_frame_time = now_mono

                # Update runtime status
                self.status.last_frame_at = datetime.now(timezone.utc)
                self.status.actual_fps = self._fps_calc.get_fps()
                self.status.frame_age_ms = 0.0  # just received
                self.status.latency_ms = 0.0    # no timestamp in stream; use frame_age as proxy
                if self._connected_at:
                    self.status.uptime_seconds = now_mono - self._connected_at

                # Low FPS detection
                target = settings.default_target_fps
                fps_threshold = target * settings.low_fps_ratio
                actual = self.status.actual_fps

                if actual > 0 and actual < fps_threshold:
                    if low_fps_start is None:
                        low_fps_start = now_mono
                    elif (now_mono - low_fps_start > settings.low_fps_duration_seconds
                          and now_mono - last_fps_alert > settings.alert_cooldown_seconds
                          and alert_service):
                        last_fps_alert = now_mono
                        try:
                            await alert_service.emit(
                                self.camera_id, EventType.LOW_FPS, Severity.WARNING,
                                f"Camera {self.camera_name} LOW FPS: {actual:.1f} (threshold: {fps_threshold:.1f})",
                                metric_name="actual_fps", metric_value=actual, threshold=fps_threshold
                            )
                        except Exception:
                            pass
                else:
                    low_fps_start = None

            else:
                # No frame received — update frame age
                age_ms = (now_mono - last_frame_time) * 1000
                self.status.frame_age_ms = age_ms

                # Timeout check
                if now_mono - last_frame_time > settings.no_frame_timeout_seconds:
                    return True  # → disconnected

            await asyncio.sleep(0.001)  # Yield to event loop

        return False  # stopped normally

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        """Blocking: open RTSP capture. Run in executor."""
        try:
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        except Exception as e:
            logger.error("[%s] Error opening capture: %s", self.camera_name, e)
            return None
