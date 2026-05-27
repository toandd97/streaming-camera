from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "Camera Monitoring System"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    # MongoDB
    mongo_uri: str = "mongodb://mongo:27017"
    mongo_db_name: str = "camera_monitoring"

    # MediaMTX integration
    # Internal API (container-to-container) for status polling
    mediamtx_api_url: str = "http://mediamtx:9997"
    # Public-facing HLS base URL (browser uses this to load video)
    mediamtx_hls_base_url: str = "http://localhost:8888"

    # Stream status polling interval
    mediamtx_poll_interval_seconds: float = 5.0

    # Default FPS settings (kept for API compatibility)
    default_target_fps: int = 10
    default_display_fps: int = 5
    max_display_fps: int = 15

    # Alert thresholds
    cpu_alert_threshold: float = 90.0
    memory_alert_threshold: float = 85.0
    resource_alert_duration_seconds: float = 30.0
    alert_cooldown_seconds: float = 60.0

    # Telegram (optional)
    telegram_enabled: bool = False
    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "ALERT_TELEGRAM_TOKEN"),
    )
    telegram_chat_id: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_CHAT_ID", "ALERT_TELEGRAM_CHAT_ID"),
    )
    alert_project_name: str = "streaming-camera"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
