"""
Camera CRUD routes — /api/v1/cameras
"""
import logging
from typing import List
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_database
from app.schemas.camera_schema import CameraCreate, CameraUpdate, CameraResponse, DisplayFpsUpdate
from app.services.camera_service import CameraService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cameras", tags=["cameras"])


def get_camera_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> CameraService:
    return CameraService(db)


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(
    data: CameraCreate,
    svc: CameraService = Depends(get_camera_service),
):
    """Register a new camera and start streaming."""
    return await svc.create_camera(data)


@router.get("", response_model=List[CameraResponse])
async def list_cameras(
    svc: CameraService = Depends(get_camera_service),
):
    """List all cameras with merged runtime status. Use this for dashboard polling."""
    return await svc.list_cameras()


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: str,
    svc: CameraService = Depends(get_camera_service),
):
    """Get one camera with runtime status."""
    return await svc.get_camera(camera_id)


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    data: CameraUpdate,
    svc: CameraService = Depends(get_camera_service),
):
    """
    Update camera config.
    - RTSP URL change triggers worker restart.
    - Name/display_fps change applies without restart.
    """
    return await svc.update_camera(camera_id, data)


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: str,
    svc: CameraService = Depends(get_camera_service),
):
    """Stop worker and delete camera from database."""
    return await svc.delete_camera(camera_id)


@router.get("/{camera_id}/status")
async def get_camera_status(
    camera_id: str,
    svc: CameraService = Depends(get_camera_service),
):
    """Get runtime status only (useful for debugging, prefer GET /cameras for dashboard)."""
    return await svc.get_camera_status(camera_id)


@router.patch("/{camera_id}/display-fps", response_model=CameraResponse)
async def update_display_fps(
    camera_id: str,
    data: DisplayFpsUpdate,
    svc: CameraService = Depends(get_camera_service),
):
    """
    Hot-update display FPS. Applied immediately to MJPEG endpoint.
    No RTSP connection restart.
    """
    return await svc.update_display_fps(camera_id, data.display_fps)
