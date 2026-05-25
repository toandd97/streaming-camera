"""
MJPEG streaming endpoint — /api/v1/streams/{camera_id}/mjpeg

Browser uses: <img src="/api/v1/streams/{camera_id}/mjpeg" />

The generator yields JPEG frames at display_fps rate.
When no frame is available, yields a blank placeholder frame.
"""
import asyncio
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.stream_manager import stream_manager
from app.utils.image_utils import frame_to_jpeg, get_blank_frame
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/streams", tags=["streams"])

BOUNDARY = b"frame"
CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame"


async def mjpeg_generator(camera_id: str):
    """Async generator that yields MJPEG multipart frames."""
    while True:
        worker_frame = stream_manager.get_latest_frame(camera_id)
        runtime = stream_manager.get_status(camera_id)
        display_fps = runtime["display_fps"] if runtime else settings.default_display_fps

        try:
            if worker_frame is not None:
                jpeg = frame_to_jpeg(worker_frame, quality=settings.mjpeg_jpeg_quality)
            else:
                jpeg = get_blank_frame()

            # MJPEG multipart format
            header = (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n"
                b"\r\n"
            )
            yield header + jpeg + b"\r\n"

        except Exception as e:
            logger.error("MJPEG generator error for camera %s: %s", camera_id, e)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + get_blank_frame() + b"\r\n"

        # Sleep based on display_fps
        sleep_time = 1.0 / max(display_fps, 1)
        await asyncio.sleep(sleep_time)


@router.get("/{camera_id}/mjpeg")
async def stream_mjpeg(camera_id: str):
    """
    MJPEG streaming endpoint.
    Use as: <img src="/api/v1/streams/{camera_id}/mjpeg">
    """
    return StreamingResponse(
        mjpeg_generator(camera_id),
        media_type=CONTENT_TYPE,
    )
