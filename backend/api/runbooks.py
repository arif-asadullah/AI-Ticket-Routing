"""Runbooks API — fetch runbook content (steps) for display."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import require_any_authenticated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runbooks", tags=["runbooks"])


@router.get("/{runbook_id}")
async def get_runbook(
    runbook_id: str,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """Return a runbook's content (title, category, steps). Any authenticated user."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    doc = db.collection("runbooks").get(runbook_id)
    if doc is None:
        raise HTTPException(404, "Runbook not found")

    return {
        "id": doc["_key"],
        "title": doc.get("title"),
        "category": doc.get("category"),
        "steps": doc.get("steps", []),
    }
