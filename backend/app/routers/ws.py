"""WebSocket endpoint for real-time simulation progress updates."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.simulation import SimulationResult

log = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/simulations/{result_id}")
async def simulation_progress_ws(websocket: WebSocket, result_id: uuid.UUID):
    """Subscribe to real-time progress updates for a simulation.

    The client connects, and the server:
    1. Sends the current status from DB immediately.
    2. Listens on Redis pub/sub channel ``simulation:{result_id}`` for updates.
    3. Forwards each message to the WebSocket client as JSON.

    The connection closes automatically when the simulation reaches a terminal
    state (completed / failed / cancelled) or the client disconnects.
    """
    await websocket.accept()

    # Send current state first
    async with async_session() as db:
        result = await db.get(SimulationResult, result_id)
        if not result:
            await websocket.send_json({"error": "仿真任务不存在"})
            await websocket.close()
            return
        await websocket.send_json({
            "id": str(result.id),
            "status": result.status,
            "progress": result.progress,
            "message": "",
        })
        # If already terminal, close immediately
        if result.status in ("completed", "failed", "cancelled"):
            await websocket.close()
            return

    # Subscribe to Redis channel
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"simulation:{result_id}"
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), timeout=30.0)
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    parsed = json.loads(data)
                else:
                    parsed = json.loads(data.decode())
                await websocket.send_json(parsed)

                # Close on terminal state
                if parsed.get("status") in ("completed", "failed", "cancelled"):
                    break
    except (WebSocketDisconnect, asyncio.TimeoutError, asyncio.CancelledError):
        pass
    except Exception:
        log.exception("WebSocket error for simulation %s", result_id)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.close()
        try:
            await websocket.close()
        except Exception:
            pass
