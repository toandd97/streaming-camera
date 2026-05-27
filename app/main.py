"""
FastAPI application entry point.

Startup sequence:
    1. Setup logging
    2. Connect MongoDB
    3. Create indexes
    4. Initialize AlertService
    5. Load enabled cameras → start StreamManager
    6. Start MetricsMonitor background task

Shutdown sequence:
    1. Stop MetricsMonitor
    2. Stop all StreamWorkers
    3. Close MongoDB connection

Serves:
    - /api/v1/* — REST + WebSocket API
    - /docs      — Swagger UI
    - /          — Web dashboard (static HTML)
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.logging import setup_logging
from app.core.config import settings
from app.db.mongodb import connect_db, close_db, get_database
from app.db.indexes import create_indexes
from app.services.stream_manager import stream_manager
from app.services.alert_service import init_alert_service
from app.services.metrics_service import metrics_monitor
from app.services.telegram_config_service import load_telegram_configuration
from app.api.v1.router import router as v1_router

setup_logging()
logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup → yield → shutdown."""
    # ---- STARTUP ----
    logger.info("=== %s starting (env: %s) ===", settings.app_name, settings.app_env)

    await connect_db()
    db = get_database()
    await create_indexes(db)

    await load_telegram_configuration(db)
    init_alert_service(db)
    logger.info("AlertService initialized")

    # load_on_startup also starts the MediaMTX status poller (1 task for all cameras)
    await stream_manager.load_on_startup(db)
    logger.info("StreamManager loaded — %d cameras registered", len(stream_manager._configs))

    metrics_monitor.start()
    logger.info("MetricsMonitor started")

    logger.info("=== Startup complete. API at http://0.0.0.0:8000%s ===", settings.api_prefix)

    yield

    # ---- SHUTDOWN ----
    logger.info("=== Shutting down ===")
    await metrics_monitor.stop()
    await stream_manager.stop_all()
    await close_db()
    logger.info("=== Shutdown complete ===")


app = FastAPI(
    title=settings.app_name,
    description="RTSP Camera Management & Streaming Monitoring System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount API v1
app.include_router(v1_router)

# Serve static web UI
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(str(WEB_DIR / "index.html"))
