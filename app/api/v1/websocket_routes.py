"""
WebSocket dashboard endpoint — WS /api/v1/ws/dashboard

Clients connect and receive:
  - camera_status_snapshot every 1 second
  - system_metrics every 3 seconds
  - stream_event immediately when events occur (via AlertService → WebSocketManager)
"""
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import ws_manager
from app.services.stream_manager import stream_manager
from app.services.metrics_service import get_system_metrics
from app.core.constants import WS_CAMERA_STATUS_SNAPSHOT, WS_SYSTEM_METRICS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/dashboard")
async def ws_dashboard(ws: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Sends camera status every 1s and system metrics every 3s.
    Stream events are pushed immediately via WebSocketManager.broadcast().
    """
    await ws_manager.connect(ws)
    ticker = 0

    try:
        while True:
            # 1. Camera status snapshot every 1 second
            statuses = stream_manager.get_all_statuses()
            await ws.send_json({
                "type": WS_CAMERA_STATUS_SNAPSHOT,
                "data": list(statuses.values()),
            })

            # 2. System metrics every 3 seconds (every 3rd tick)
            if ticker % 3 == 0:
                metrics = get_system_metrics(active_streams=stream_manager.active_count)
                await ws.send_json({
                    "type": WS_SYSTEM_METRICS,
                    "data": metrics.model_dump(),
                })

            ticker += 1
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        await ws_manager.disconnect(ws)
