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


class MetricsMonitor:
    """
    Background task that periodically samples metrics and emits alerts
    when CPU/RAM thresholds are exceeded for a sustained duration.
    """

    def __init__(self):
        self._cpu_high_since: Optional[float] = None
        self._ram_high_since: Optional[float] = None
        self._task: Optional[asyncio.Task] = None
        
        # Cache metrics so get_system_metrics doesn't steal psutil intervals
        self.last_cpu_percent = 0.0
        self.last_memory_percent = 0.0
        self.last_memory_used_mb = 0.0
        self.last_gpu_percent: Optional[float] = None
        self.last_gpu_memory_used_mb: Optional[float] = None

    def start(self) -> None:
        # Initialize the first interval
        psutil.cpu_percent(interval=None)
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
        while True:
            try:
                await asyncio.sleep(5)
                await self._sample_and_alert()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("MetricsMonitor error: %s", e)

    async def _sample_and_alert(self) -> None:
        """Sample resources once and emit sustained CPU or memory alerts."""
        from app.services.alert_service import get_alert_service
        from app.core.constants import EventType, Severity

        now = time.monotonic()
        alert_svc = get_alert_service()

        # Non-blocking sampling keeps the async API responsive.
        # Calling this here reliably gets the average over the last 5s sleep.
        self.last_cpu_percent = psutil.cpu_percent(interval=None)
        
        mem = psutil.virtual_memory()
        self.last_memory_percent = mem.percent
        self.last_memory_used_mb = mem.used / 1024 / 1024
        
        gpu_pct, gpu_mem = get_gpu_metrics()
        self.last_gpu_percent = gpu_pct
        self.last_gpu_memory_used_mb = gpu_mem

        # Check CPU alert
        if self.last_cpu_percent >= settings.cpu_alert_threshold:
            if self._cpu_high_since is None:
                self._cpu_high_since = now
            elif now - self._cpu_high_since >= settings.resource_alert_duration_seconds:
                await alert_svc.emit(
                    camera_id="system",
                    event_type=EventType.HIGH_CPU,
                    severity=Severity.CRITICAL,
                    message=f"HIGH CPU: {self.last_cpu_percent:.1f}% (threshold: {settings.cpu_alert_threshold}%)",
                    metric_name="cpu_percent",
                    metric_value=self.last_cpu_percent,
                    threshold=settings.cpu_alert_threshold,
                )
                # DO NOT reset self._cpu_high_since = None here. 
                # Let AlertService handle the 60s cooldown.
        else:
            self._cpu_high_since = None

        # Check RAM alert
        if self.last_memory_percent >= settings.memory_alert_threshold:
            if self._ram_high_since is None:
                self._ram_high_since = now
            elif now - self._ram_high_since >= settings.resource_alert_duration_seconds:
                await alert_svc.emit(
                    camera_id="system",
                    event_type=EventType.HIGH_MEMORY,
                    severity=Severity.CRITICAL,
                    message=f"HIGH MEMORY: {self.last_memory_percent:.1f}% (threshold: {settings.memory_alert_threshold}%)",
                    metric_name="memory_percent",
                    metric_value=self.last_memory_percent,
                    threshold=settings.memory_alert_threshold,
                )
        else:
            self._ram_high_since = None


# Singleton
metrics_monitor = MetricsMonitor()

def get_system_metrics(active_streams: int = 0) -> SystemMetricsResponse:
    """Collect and return current system metrics from the cached monitor."""
    return SystemMetricsResponse(
        cpu_percent=round(metrics_monitor.last_cpu_percent, 1),
        memory_percent=round(metrics_monitor.last_memory_percent, 1),
        memory_used_mb=round(metrics_monitor.last_memory_used_mb, 1),
        gpu_available=_gpu_available,
        gpu_percent=round(metrics_monitor.last_gpu_percent, 1) if metrics_monitor.last_gpu_percent is not None else None,
        gpu_memory_used_mb=round(metrics_monitor.last_gpu_memory_used_mb, 1) if metrics_monitor.last_gpu_memory_used_mb is not None else None,
        active_streams=active_streams,
    )
