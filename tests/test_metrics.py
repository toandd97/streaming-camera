"""
Tests for system metrics service.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.constants import EventType


def test_get_system_metrics_structure():
    """SystemMetricsResponse should have required fields."""
    from app.services.metrics_service import get_system_metrics

    metrics = get_system_metrics(active_streams=3)

    assert hasattr(metrics, "cpu_percent")
    assert hasattr(metrics, "memory_percent")
    assert hasattr(metrics, "memory_used_mb")
    assert hasattr(metrics, "gpu_available")
    assert hasattr(metrics, "active_streams")
    assert metrics.active_streams == 3


def test_get_system_metrics_cpu_range():
    """CPU percent should be between 0 and 100."""
    from app.services.metrics_service import get_system_metrics

    metrics = get_system_metrics()
    assert 0 <= metrics.cpu_percent <= 100


def test_get_system_metrics_ram_range():
    """Memory percent should be between 0 and 100."""
    from app.services.metrics_service import get_system_metrics

    metrics = get_system_metrics()
    assert 0 <= metrics.memory_percent <= 100


def test_get_system_metrics_no_gpu():
    """When pynvml is not available, gpu_available should be False."""
    from app.services.metrics_service import get_system_metrics, _gpu_available

    metrics = get_system_metrics()

    if not _gpu_available:
        assert metrics.gpu_available is False
        assert metrics.gpu_percent is None
        assert metrics.gpu_memory_used_mb is None


def test_metrics_schema_serialization():
    """SystemMetricsResponse should serialize to dict correctly."""
    from app.schemas.metrics_schema import SystemMetricsResponse

    m = SystemMetricsResponse(
        cpu_percent=42.5,
        memory_percent=61.2,
        memory_used_mb=8192.0,
        gpu_available=False,
        gpu_percent=None,
        gpu_memory_used_mb=None,
        active_streams=4,
    )

    d = m.model_dump()
    assert d["cpu_percent"] == 42.5
    assert d["memory_percent"] == 61.2
    assert d["gpu_available"] is False
    assert d["active_streams"] == 4


@pytest.mark.asyncio
async def test_metrics_monitor_emits_high_cpu_alert():
    """Sustained high CPU is routed to AlertService for Telegram handling."""
    from app.services.metrics_service import MetricsMonitor

    monitor = MetricsMonitor()
    monitor._cpu_high_since = 1.0
    alert_service = MagicMock()
    alert_service.emit = AsyncMock()

    with (
        patch("app.services.alert_service.get_alert_service", return_value=alert_service),
        patch("app.services.metrics_service.time.monotonic", return_value=100.0),
        patch("app.services.metrics_service.psutil.cpu_percent", return_value=99.0),
        patch("app.services.metrics_service.psutil.virtual_memory") as memory,
        patch("app.services.metrics_service.settings.resource_alert_duration_seconds", 30.0),
    ):
        memory.return_value.percent = 10.0
        await monitor._sample_and_alert()

    alert_service.emit.assert_awaited_once()
    assert alert_service.emit.await_args.kwargs["event_type"] == EventType.HIGH_CPU
    assert alert_service.emit.await_args.kwargs["metric_value"] == 99.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route_name", "random_value", "event_type", "threshold"),
    [
        ("simulate_cpu", 94.7, EventType.HIGH_CPU, 90.0),
        ("simulate_memory", 88.3, EventType.HIGH_MEMORY, 85.0),
    ],
)
async def test_manual_alert_simulation_is_randomized_and_bypasses_cooldown(
    route_name, random_value, event_type, threshold
):
    from app.api.v1 import metrics_routes

    alert_service = MagicMock()
    alert_service.emit = AsyncMock()
    with (
        patch("app.services.alert_service.get_alert_service", return_value=alert_service),
        patch("app.api.v1.metrics_routes.random.uniform", return_value=random_value),
    ):
        response = await getattr(metrics_routes, route_name)()

    args = alert_service.emit.await_args.kwargs
    assert args["event_type"] == event_type
    assert args["metric_value"] == random_value
    assert args["threshold"] == threshold
    assert args["bypass_cooldown"] is True
    assert f"{random_value:.1f}%" in response.message
