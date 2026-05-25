"""
Tests for system metrics service.
"""
import pytest
from unittest.mock import patch, MagicMock


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
