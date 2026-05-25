"""
System metrics endpoint — /api/v1/system/metrics
"""
from fastapi import APIRouter
from app.schemas.metrics_schema import SystemMetricsResponse
from app.services.metrics_service import get_system_metrics
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/system", tags=["metrics"])


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_metrics():
    """Return current CPU, RAM, GPU metrics and active stream count."""
    return get_system_metrics(active_streams=stream_manager.active_count)
