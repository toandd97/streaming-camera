"""
API v1 router — aggregates all v1 route modules.

To add v2: create app/api/v2/router.py and mount separately in main.py.
This file (v1) is never touched when adding v2.
"""
from fastapi import APIRouter

from app.api.v1.camera_routes import router as camera_router
from app.api.v1.stream_routes import router as stream_router
from app.api.v1.metrics_routes import router as metrics_router
from app.api.v1.event_routes import router as event_router
from app.api.v1.websocket_routes import router as ws_router

router = APIRouter(prefix="/api/v1")

router.include_router(camera_router)
router.include_router(stream_router)
router.include_router(metrics_router)
router.include_router(event_router)
router.include_router(ws_router)
