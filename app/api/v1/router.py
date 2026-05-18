"""
app/api/v1/router.py

Aggregates all v1 routers into one. main.py only imports this.
Adding a new domain = one line here.
"""

from fastapi import APIRouter

from app.api.v1 import auth, health, transcriptions

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(transcriptions.router)