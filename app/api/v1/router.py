"""
app/api/v1/router.py
"""

from fastapi import APIRouter

from app.api.v1 import analytics, auth, health, transcriptions, webhooks, ws

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(transcriptions.router)
api_router.include_router(webhooks.router)
api_router.include_router(analytics.router)
api_router.include_router(ws.router)