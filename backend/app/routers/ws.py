"""WebSocket endpoint for real-time simulation progress updates.

Supports two modes:
- **Redis mode**: Subscribe to Redis pub/sub for instant updates (when Redis available).
- **DB polling mode**: Poll the database every 2 seconds (fallback when Redis unavailable).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.simulation import SimulationResult
from app.utils.redis_check import is_redis_available

log = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def _send_current_state(websocket: WebSocket, result_id: uuid.UUID) -> str | None:
    """Send current simulation state from DB. Returns status or None if not found."""
    async with async_session() as db:
        result = await db.get(SimulationResult, result_id)
        if not result:
            await websocket.send_json({"error": "仿真任务不存在"})
            return None
        await websocket.send_json({
            "id": str(result.id),
            "status": result.status,
            "progress": result.progress,
            "message": "",
        })
        return result.status


async def _ws_redis_pubsub(websocket: WebSocket, result_id: uuid.UUID) -> None:
    """Listen on Redis pub/sub channel and forward messages to WebSocket."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"simulation:{result_id}"
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                timeout=30.0,
            )
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    parsed = json.loads(data)
                else:
                    parsed = json.loads(data.decode())
                await websocket.send_json(parsed)

                if parsed.get("status") in ("completed", "failed", "cancelled"):
                    break
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.close()


async def _ws_db_polling(websocket: WebSocket, result_id: uuid.UUID) -> None:
    """Poll the database for progress updates and send to WebSocket."""
    last_progress = -1
    last_status = ""

    while True:
        await asyncio.sleep(2)
        async with async_session() as db:
            result = await db.get(SimulationResult, result_id)
            if not result:
                break

            # Only send when there's a change
            if result.progress != last_progress or result.status != last_status:
                last_progress = result.progress
                last_status = result.status
                await websocket.send_json({
                    "id": str(result.id),
                    "status": result.status,
                    "progress": result.progress,
                    "message": "",
                })

            if result.status in ("completed", "failed", "cancelled"):
                break


@router.websocket("/ws/simulations/{result_id}")
async def simulation_progress_ws(websocket: WebSocket, result_id: uuid.UUID):
    """Subscribe to real-time progress updates for a simulation.

    Automatically selects Redis pub/sub or DB polling based on Redis availability.
    """
    await websocket.accept()

    # Send current state first
    status = await _send_current_state(websocket, result_id)
    if status is None:
        await websocket.close()
        return
    if status in ("completed", "failed", "cancelled"):
        await websocket.close()
        return

    try:
        if is_redis_available():
            await _ws_redis_pubsub(websocket, result_id)
        else:
            await _ws_db_polling(websocket, result_id)
    except (WebSocketDisconnect, asyncio.TimeoutError, asyncio.CancelledError):
        pass
    except Exception:
        log.exception("WebSocket error for simulation %s", result_id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
