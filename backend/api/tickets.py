"""Tickets API — CRUD backed by ArangoDB with 4-classifier AI routing."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from backend.schemas.ticket import TicketCreate, TicketResponse
from backend.services.orchestrator import classify

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketResponse])
async def list_tickets(request: Request):
    """List all user-submitted tickets (excludes seed/synthetic data)."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    tickets = []
    for doc in collection.all():
        # Only show user-submitted tickets, not seed/synthetic
        if doc.get("_source") in ("seed", "synthetic"):
            continue
        tickets.append(_doc_to_response(doc))
    return tickets


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(ticket: TicketCreate, request: Request):
    """Create a new ticket and classify + route it using the 4-classifier ensemble."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    redis_client = getattr(request.app.state, "redis", None)

    # ── Run the 4-classifier pipeline ──
    result = await classify(
        title=ticket.title,
        description=ticket.description,
        db=db,
        redis_client=redis_client,
    )

    # Determine status based on confidence
    if result["confidence"] >= 0.70:
        status = "routed"
    else:
        status = "escalated"

    now = datetime.now(timezone.utc).isoformat()

    # ── Save ticket to database ──
    collection = db.collection("tickets")
    doc = collection.insert({
        "title": ticket.title,
        "description": ticket.description,
        "category": result["category"],
        "secondary_category": result["secondary_category"],
        "priority": result["priority"],
        "status": status,
        "confidence_score": result["confidence"],
        "ai_reasoning": result["reasoning"],
        "quality_score": result["quality_score"],
        "classifier_votes": result["classifier_votes"],
        "submitted_by": ticket.submitted_by,
        "routed_to": result["recommended_team"],
        "embedding": result["embedding"],
        "created_at": now,
        "resolved_at": None,
        "_source": "user",
    })

    ticket_key = doc["_key"]

    # ── Create edges ──
    try:
        # assigned_to edge (ticket → team)
        if result["recommended_team"]:
            # Look up team key from name
            team_key = _lookup_team_key(db, result["recommended_team"])
            if team_key:
                db.collection("assigned_to").insert({
                    "_from": f"tickets/{ticket_key}",
                    "_to": f"teams/{team_key}",
                })
    except Exception as exc:
        logger.warning("Failed to create edges for ticket %s: %s", ticket_key, exc)

    # ── Log to audit_log ──
    try:
        db.collection("audit_log").insert({
            "ticket_id": ticket_key,
            "action": "classified" if status == "routed" else "escalated",
            "actor": f"ai-{result['degradation_level']}-classifier-ensemble",
            "old_value": None,
            "new_value": {
                "category": result["category"],
                "priority": result["priority"],
                "team": result["recommended_team"],
            },
            "confidence_score": result["confidence"],
            "confidence_signals": {
                "llm": result["classifier_votes"].get("llm", {}).get("confidence"),
                "knn": result["classifier_votes"].get("knn", {}).get("confidence"),
                "centroid": result["classifier_votes"].get("centroid", {}).get("confidence"),
                "keyword": result["classifier_votes"].get("keyword", {}).get("confidence"),
            },
            "reasoning": result["reasoning"],
            "created_at": now,
        })
    except Exception as exc:
        logger.warning("Failed to write audit log for ticket %s: %s", ticket_key, exc)

    logger.info(
        "Ticket %s: %s → %s (%.1f%% confidence, %s, level=%d, %dms)",
        ticket_key, result["category"], result["recommended_team"],
        result["confidence"] * 100, result["agreement"],
        result["degradation_level"], result["processing_time_ms"],
    )

    return TicketResponse(
        id=ticket_key,
        title=ticket.title,
        description=ticket.description,
        category=result["category"],
        secondary_category=result["secondary_category"],
        priority=result["priority"],
        status=status,
        confidence_score=result["confidence"],
        ai_reasoning=result["reasoning"],
        quality_score=result["quality_score"],
        classifier_votes=result["classifier_votes"],
        submitted_by=ticket.submitted_by,
        routed_to=result["recommended_team"],
        suggested_resolution=result["suggested_resolution"],
        resolution_effectiveness=result["resolution_effectiveness"],
        suggested_runbook=result["suggested_runbook"],
        recommended_expert=result["recommended_expert"],
        created_at=now,
        resolved_at=None,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, request: Request):
    """Get a single ticket by ID."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    return _doc_to_response(doc)


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: str, request: Request):
    """Delete a ticket."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    if not collection.has(ticket_id):
        raise HTTPException(404, "Ticket not found")
    collection.delete(ticket_id)


def _doc_to_response(doc: dict) -> TicketResponse:
    """Convert ArangoDB document to TicketResponse."""
    return TicketResponse(
        id=doc["_key"],
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        category=doc.get("category"),
        secondary_category=doc.get("secondary_category"),
        priority=doc.get("priority", "medium"),
        status=doc.get("status", "open"),
        confidence_score=doc.get("confidence_score"),
        ai_reasoning=doc.get("ai_reasoning"),
        quality_score=doc.get("quality_score"),
        classifier_votes=doc.get("classifier_votes"),
        submitted_by=doc.get("submitted_by"),
        routed_to=doc.get("routed_to"),
        suggested_resolution=doc.get("suggested_resolution"),
        resolution_effectiveness=doc.get("resolution_effectiveness"),
        suggested_runbook=doc.get("suggested_runbook"),
        recommended_expert=doc.get("recommended_expert"),
        created_at=doc.get("created_at"),
        resolved_at=doc.get("resolved_at"),
    )


def _lookup_team_key(db, team_name: str) -> str | None:
    """Find team _key from team name."""
    try:
        for doc in db.collection("teams").all():
            if doc.get("name") == team_name:
                return doc["_key"]
    except Exception:
        pass
    return None
