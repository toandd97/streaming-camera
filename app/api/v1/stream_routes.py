"""
HLS stream info endpoint — /api/v1/streams/{camera_id}/hls-info

Returns the HLS URL for a camera so the frontend can play it directly
via hls.js or native browser HLS support.

Architecture:
    Browser → GET /api/v1/streams/{id}/hls-info → gets HLS URL
    Browser → hls.js loads http://localhost:8888/{path}/index.m3u8 directly
    MediaMTX → serves HLS segments (no Python involved in video delivery)

This scales to 80+ cameras because Python is NOT in the video pipeline.
"""
import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.services.stream_manager import stream_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/streams", tags=["streams"])


class HLSInfo(BaseModel):
    camera_id: str
    hls_url: Optional[str]
    rtsp_path: str
    available: bool


@router.get("/{camera_id}/hls-info", response_model=HLSInfo)
async def get_hls_info(camera_id: str):
    """
    Get HLS stream URL for a camera.
    The browser uses this URL to load video via hls.js.
    """
    hls_url = stream_manager.get_hls_url(camera_id)
    status_data = stream_manager.get_status(camera_id)

    if hls_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found or not registered"
        )

    cam_status = status_data.get("status", "STOPPED") if status_data else "STOPPED"
    available = cam_status == "CONNECTED"

    # Extract rtsp_path from hls_url for convenience
    try:
        rtsp_path = hls_url.rsplit("/", 2)[-2]
    except Exception:
        rtsp_path = ""

    return HLSInfo(
        camera_id=camera_id,
        hls_url=hls_url if available else None,
        rtsp_path=rtsp_path,
        available=available,
    )
