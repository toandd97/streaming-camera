"""
Logging configuration — chuẩn Python logging convention.

Convention:
    - Dùng logging.config.dictConfig để cấu hình tập trung
    - Mỗi module tự lấy logger riêng: logger = logging.getLogger(__name__)
    - Không dùng print() trong codebase
    - local env: colored text output
    - production env: JSON structured output (dễ ingest vào ELK/Loki)
"""
import logging
import logging.config
import sys
from app.core.config import settings

LOG_LEVEL = "DEBUG" if settings.app_env == "local" else "INFO"

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
        "access": {
            "format": "%(asctime)s | ACCESS | %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": sys.stdout,
        },
        "access": {
            "class": "logging.StreamHandler",
            "formatter": "access",
            "stream": sys.stdout,
        },
    },
    "loggers": {
        "app": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["default"],
        "level": "WARNING",
    },
}


def setup_logging() -> None:
    """Call once at application startup."""
    logging.config.dictConfig(LOGGING_CONFIG)
