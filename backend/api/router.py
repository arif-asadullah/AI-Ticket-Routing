"""Central API router — include all route modules here."""

from fastapi import APIRouter

from backend.api.auth import router as auth_router
from backend.api.health import router as health_router
from backend.api.tickets import router as tickets_router
from backend.api.chat import router as chat_router
from backend.api.stats import router as stats_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(tickets_router)
api_router.include_router(chat_router)
api_router.include_router(stats_router)
