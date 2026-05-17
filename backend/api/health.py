"""Health check endpoint."""

from fastapi import APIRouter, Request

from backend.services.orchestrator import check_health

router = APIRouter()

LEVEL_MESSAGES = {
    4: "All systems operational",
    3: "Operating without historical data — LLM + keyword only",
    2: "LLM offline — using KNN, centroid, and keyword classifiers",
    1: "Emergency mode — keyword classification only",
}


@router.get("/health")
async def health(request: Request) -> dict:
    """Return the status of backing services and degradation level."""
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

    # Get degradation level from orchestrator health check
    health_status = await check_health(db=db, redis_client=redis_client)
    level = health_status["level"]

    # Count pending_human tickets
    pending_human_count = 0
    if db is not None:
        try:
            cursor = db.aql.execute(
                "FOR t IN tickets FILTER t.status == 'pending_human' "
                "COLLECT WITH COUNT INTO c RETURN c"
            )
            pending_human_count = next(cursor, 0)
        except Exception:
            pass

    from backend.services.circuit_breaker import ollama_breaker

    return {
        "status": "ok" if level == 4 else "degraded",
        "arango": arango_status,
        "redis": redis_status,
        "ollama": "connected" if health_status["ollama"] else "unavailable",
        "ollama_circuit_breaker": ollama_breaker.get_status(),
        "degradation_level": level,
        "message": LEVEL_MESSAGES.get(level, "Unknown"),
        "pending_human_count": pending_human_count,
    }
