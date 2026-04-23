"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.core.config import settings
from backend.services.cache import close_redis, connect_redis
from backend.services.database import close_arango, connect_arango
from backend.services.schema import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logging.basicConfig(level=settings.LOG_LEVEL)
    logger = logging.getLogger(__name__)

    logger.info("Starting AI-Ticket-Routing backend...")

    # Connect to backing services (graceful if unavailable)
    app.state.arango_db = connect_arango()
    app.state.redis = await connect_redis()

    # Initialize full schema (collections, edges, graph, indexes)
    if app.state.arango_db is not None:
        init_schema(app.state.arango_db)

    yield

    # Shutdown
    logger.info("Shutting down...")
    close_arango()
    await close_redis()


app = FastAPI(
    title="AI-Ticket-Routing",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
