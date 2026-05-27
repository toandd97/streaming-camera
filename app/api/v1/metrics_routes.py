"""
System metrics and simulation endpoints — /api/v1/system
"""
import random

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_database
from app.schemas.metrics_schema import (
    SystemMetricsResponse,
    TelegramConfigResponse,
    TelegramConfigUpdate,
)
from app.common.response import MessageResponse
from app.services.metrics_service import get_system_metrics
from app.services.stream_manager import stream_manager
from app.services.telegram_config_service import (
    get_telegram_configuration,
    update_telegram_configuration,
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_metrics():
    """Return current CPU, RAM, GPU metrics and active stream count."""
    return get_system_metrics(active_streams=stream_manager.active_count)


@router.get("/telegram-config", response_model=TelegramConfigResponse)
async def get_telegram_config():
    """Return Telegram status without exposing the saved bot token."""
    return get_telegram_configuration()


@router.put("/telegram-config", response_model=TelegramConfigResponse)
async def update_telegram_config(
    data: TelegramConfigUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Send a test message, then save and enable a verified destination."""
    return await update_telegram_configuration(db, data)


@router.post("/simulate/disconnect/{camera_id}", response_model=MessageResponse)
async def simulate_disconnect(camera_id: str):
    """Simulate camera disconnection by forcing it offline."""
    await stream_manager.simulate_disconnect(camera_id)
    return MessageResponse(message=f"Simulated disconnection for camera {camera_id}")


@router.post("/simulate/reconnect/{camera_id}", response_model=MessageResponse)
async def simulate_reconnect(camera_id: str):
    """Restore actual camera status."""
    await stream_manager.simulate_reconnect(camera_id)
    return MessageResponse(message=f"Restored actual status for camera {camera_id}")


@router.post("/simulate/cpu", response_model=MessageResponse)
async def simulate_cpu():
    """Simulate a high CPU usage alert immediately."""
    from app.services.alert_service import get_alert_service
    from app.core.constants import EventType, Severity
    value = round(random.uniform(90.0, 99.0), 1)
    alert_svc = get_alert_service()
    await alert_svc.emit(
        camera_id="system",
        event_type=EventType.HIGH_CPU,
        severity=Severity.CRITICAL,
        message=f"SIMULATED HIGH CPU: {value:.1f}% (threshold: 90.0%)",
        metric_name="cpu_percent",
        metric_value=value,
        threshold=90.0,
        bypass_cooldown=True,
    )
    return MessageResponse(message=f"Simulated High CPU alert emitted: {value:.1f}%")


@router.post("/simulate/memory", response_model=MessageResponse)
async def simulate_memory():
    """Simulate a high Memory usage alert immediately."""
    from app.services.alert_service import get_alert_service
    from app.core.constants import EventType, Severity
    value = round(random.uniform(85.0, 99.0), 1)
    alert_svc = get_alert_service()
    await alert_svc.emit(
        camera_id="system",
        event_type=EventType.HIGH_MEMORY,
        severity=Severity.CRITICAL,
        message=f"SIMULATED HIGH MEMORY: {value:.1f}% (threshold: 85.0%)",
        metric_name="memory_percent",
        metric_value=value,
        threshold=85.0,
        bypass_cooldown=True,
    )
    return MessageResponse(message=f"Simulated High Memory alert emitted: {value:.1f}%")
