"""
app/api/v1/ws.py

WebSocket endpoint for real-time job status updates.

Flow:
  1. Client connects: ws://host/api/v1/ws/jobs?token=<access_token>
  2. Server verifies JWT
  3. Server subscribes to Redis channel: job_updates:<user_id>
  4. When Celery worker publishes an update, server pushes to client
  5. Client disconnects → cleanup

WHY Redis pub/sub and not polling?
Multiple API instances can serve WebSocket connections.
Redis acts as the message bus between workers and any API instance.
"""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.exceptions import InvalidTokenError
from app.core.logging import get_logger
from app.core.security import decode_token

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/jobs")
async def job_updates_ws(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    # Verify token before accepting connection
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001)
            return
    except InvalidTokenError:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    logger.info("ws_connected", user_id=user_id)

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = f"job_updates:{user_id}"
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=user_id)
    except Exception as e:
        logger.error("ws_error", user_id=user_id, error=str(e))
    finally:
        await pubsub.unsubscribe(channel)
        await redis.aclose()