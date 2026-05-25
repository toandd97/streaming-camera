from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Camera Monitoring System"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    # MongoDB
    mongo_uri: str = "mongodb://mongo:27017"
    mongo_db_name: str = "camera_monitoring"

    # Stream timeouts
    no_frame_timeout_seconds: float = 5.0
    reconnect_interval_seconds: float = 3.0
    default_target_fps: int = 10
    default_display_fps: int = 5
    max_display_fps: int = 15

    # Alert thresholds
    low_fps_ratio: float = 0.5
    low_fps_duration_seconds: float = 10.0
    cpu_alert_threshold: float = 90.0
    memory_alert_threshold: float = 85.0
    resource_alert_duration_seconds: float = 30.0
    alert_cooldown_seconds: float = 60.0

    # Telegram (optional)
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # MJPEG
    mjpeg_jpeg_quality: int = 80

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
