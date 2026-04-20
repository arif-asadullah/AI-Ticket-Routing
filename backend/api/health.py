"""Health check endpoint."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    """Return the status of backing services."""
    arango_status = "unavailable"
    redis_status = "unavailable"

    db = getattr(request.app.state, "arango_db", None)
    if db is not None:
        try:
            db.version()
            arango_status = "connected"
        except Exception:
            arango_status = "unavailable"

    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "unavailable"

    return {
        "status": "ok",
        "arango": arango_status,
        "redis": redis_status,
    }
