"""
MetricsService — collects CPU, RAM, and GPU metrics.

- psutil for CPU and memory
- pynvml for NVIDIA GPU (optional, fails gracefully)
- Background task monitors thresholds and emits HIGH_CPU/HIGH_MEMORY alerts
"""
import asyncio
import logging
import time
from typing import Optional

import psutil

from app.core.config import settings
from app.schemas.metrics_schema import SystemMetricsResponse

logger = logging.getLogger(__name__)

# GPU support via pynvml (optional)
_gpu_available = False
try:
    import pynvml
    pynvml.nvmlInit()
    _gpu_available = True
    logger.info("NVIDIA GPU detected, GPU metrics enabled")
except Exception:
    logger.info("No NVIDIA GPU detected or pynvml not available, GPU metrics disabled")


def get_gpu_metrics() -> tuple[Optional[float], Optional[float]]:
    """Returns (gpu_percent, gpu_memory_used_mb) or (None, None)."""
    if not _gpu_available:
        return None, None
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return float(util.gpu), mem.used / 1024 / 1024
    except Exception:
        return None, None


def get_system_metrics(active_streams: int = 0) -> SystemMetricsResponse:
    """Collect and return current system metrics."""
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    gpu_pct, gpu_mem = get_gpu_metrics()

    return SystemMetricsResponse(
        cpu_percent=round(cpu, 1),
        memory_percent=round(mem.percent, 1),
        memory_used_mb=round(mem.used / 1024 / 1024, 1),
        gpu_available=_gpu_available,
        gpu_percent=round(gpu_pct, 1) if gpu_pct is not None else None,
        gpu_memory_used_mb=round(gpu_mem, 1) if gpu_mem is not None else None,
        active_streams=active_streams,
    )


class MetricsMonitor:
    """
    Background task that periodically samples metrics and emits alerts
    when CPU/RAM thresholds are exceeded for a sustained duration.
    """

    def __init__(self):
        self._cpu_high_since: Optional[float] = None
        self._ram_high_since: Optional[float] = None
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="metrics-monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        """Sample every 5 seconds, alert when threshold sustained."""
        from app.services.alert_service import get_alert_service
        from app.core.constants import EventType, Severity

        while True:
            try:
                await asyncio.sleep(5)
                now = time.monotonic()
                alert_svc = get_alert_service()

                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent

                # CPU check
                if cpu > settings.cpu_alert_threshold:
                    if self._cpu_high_since is None:
                        self._cpu_high_since = now
                    elif now - self._cpu_high_since > settings.resource_alert_duration_seconds:
                        await alert_svc.emit(
                            camera_id="system",
                            event_type=EventType.HIGH_CPU,
                            severity=Severity.CRITICAL,
                            message=f"HIGH CPU: {cpu:.1f}% (threshold: {settings.cpu_alert_threshold}%)",
                            metric_name="cpu_percent",
                            metric_value=cpu,
                            threshold=settings.cpu_alert_threshold,
                        )
                        self._cpu_high_since = None  # Reset after alert
                else:
                    self._cpu_high_since = None

                # Memory check
                if mem > settings.memory_alert_threshold:
                    if self._ram_high_since is None:
                        self._ram_high_since = now
                    elif now - self._ram_high_since > settings.resource_alert_duration_seconds:
                        await alert_svc.emit(
                            camera_id="system",
                            event_type=EventType.HIGH_MEMORY,
                            severity=Severity.CRITICAL,
                            message=f"HIGH MEMORY: {mem:.1f}% (threshold: {settings.memory_alert_threshold}%)",
                            metric_name="memory_percent",
                            metric_value=mem,
                            threshold=settings.memory_alert_threshold,
                        )
                        self._ram_high_since = None
                else:
                    self._ram_high_since = None

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("MetricsMonitor error: %s", e)


# Singleton
metrics_monitor = MetricsMonitor()
