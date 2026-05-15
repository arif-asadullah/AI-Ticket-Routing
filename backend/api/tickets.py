"""Tickets API — CRUD backed by ArangoDB with 4-classifier AI routing."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import (
    get_current_user,
    require_admin,
    require_any_authenticated,
    require_engineer_or_admin,
    require_team_access,
)
from backend.schemas.ticket import TicketCreate, TicketFeedback, TicketResolve, TicketResponse, TicketStatusUpdate
from backend.services.orchestrator import classify

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketResponse])
async def list_tickets(request: Request, user: dict = Depends(get_current_user)):
    """List user-submitted tickets. Engineers see only their team's tickets."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    # Resolve engineer's team name for filtering
    user_team_name = None
    if user["role"] == "engineer" and user.get("team_key"):
        user_team_name = _team_key_to_name(db, user["team_key"])

    collection = db.collection("tickets")
    tickets = []
    for doc in collection.all():
        # Only show user-submitted tickets
        if doc.get("_source") != "user":
            continue
        # Team scoping: engineers only see tickets routed to their team
        if user["role"] == "engineer" and doc.get("routed_to") != user_team_name:
            continue
        tickets.append(_doc_to_response(doc))
    return tickets


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(
    ticket: TicketCreate,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """Create a new ticket and classify + route it using the 4-classifier ensemble."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    redis_client = getattr(request.app.state, "redis", None)

    # ── Run the 4-classifier pipeline ──
    try:
        result = await classify(
            title=ticket.title,
            description=ticket.description,
            db=db,
            redis_client=redis_client,
        )
    except Exception as exc:
        logger.error("Classification pipeline failed: %s", exc)
        raise HTTPException(500, "Classification failed. Please try again.")

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
        "submitted_by": user["email"],
        "routed_to": result["recommended_team"],
        "embedding": result["embedding"],
        "suggested_resolution": result["suggested_resolution"],
        "resolution_effectiveness": result["resolution_effectiveness"],
        "suggested_runbook": result["suggested_runbook"],
        "recommended_expert": result["recommended_expert"],
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
        submitted_by=user["email"],
        routed_to=result["recommended_team"],
        suggested_resolution=result["suggested_resolution"],
        resolution_effectiveness=result["resolution_effectiveness"],
        suggested_runbook=result["suggested_runbook"],
        recommended_expert=result["recommended_expert"],
        created_at=now,
        resolved_at=None,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Get a single ticket by ID. Engineers can only view their team's tickets."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    # Team access check for engineers
    if user["role"] == "engineer":
        user_team_name = _team_key_to_name(db, user.get("team_key"))
        if doc.get("routed_to") != user_team_name:
            raise HTTPException(403, "This ticket is not assigned to your team")

    return _doc_to_response(doc)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: str,
    update: TicketStatusUpdate,
    request: Request,
    user: dict = Depends(require_engineer_or_admin),
):
    """Update ticket status — engineer picks up, reassigns, or escalates."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    # Team access check
    await require_team_access(doc.get("routed_to"), user, db)

    valid_statuses = {"in_progress", "escalated", "routed"}
    if update.status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")

    if doc.get("status") in ("resolved", "closed"):
        raise HTTPException(400, "Cannot update status of resolved/closed ticket")

    # Prevent double pick-up — if ticket is already picked up by another engineer
    if update.status == "in_progress" and doc.get("picked_up_by"):
        if doc["picked_up_by"] != user["email"]:
            raise HTTPException(
                409,
                f"Ticket already picked up by {doc['picked_up_by']}"
            )

    now = datetime.now(timezone.utc).isoformat()
    old_status = doc.get("status")

    # Build update fields
    update_fields = {
        "_key": ticket_id,
        "status": update.status,
    }

    # Track who picked up / release on escalate
    if update.status == "in_progress":
        update_fields["picked_up_by"] = user["email"]
    elif update.status in ("escalated", "routed"):
        update_fields["picked_up_by"] = None

    # If reassigning to a different team
    new_team = None
    if update.assigned_to:
        new_team = update.assigned_to
        update_fields["routed_to"] = new_team

        # Update assigned_to edge
        try:
            team_key = _lookup_team_key(db, new_team)
            if team_key:
                # Remove old assigned_to edge
                query = """
                FOR e IN assigned_to
                    FILTER e._from == CONCAT("tickets/", @ticket_id)
                    REMOVE e IN assigned_to
                """
                db.aql.execute(query, bind_vars={"ticket_id": ticket_id})
                # Create new edge
                db.collection("assigned_to").insert({
                    "_from": f"tickets/{ticket_id}",
                    "_to": f"teams/{team_key}",
                })
        except Exception as exc:
            logger.warning("Failed to update assigned_to edge: %s", exc)

    collection.update(update_fields)

    # Audit log
    try:
        db.collection("audit_log").insert({
            "ticket_id": ticket_id,
            "action": update.status,
            "actor": user["email"],
            "old_value": {"status": old_status, "team": doc.get("routed_to")},
            "new_value": {"status": update.status, "team": new_team or doc.get("routed_to")},
            "confidence_score": None,
            "reasoning": f"Status changed by {user['email']}",
            "created_at": now,
        })
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)

    logger.info(
        "Ticket %s: %s → %s by %s",
        ticket_id, old_status, update.status, user["email"],
    )

    updated = collection.get(ticket_id)
    return _doc_to_response(updated)


@router.post("/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(
    ticket_id: str,
    resolve: TicketResolve,
    request: Request,
    user: dict = Depends(require_engineer_or_admin),
):
    """Resolve a ticket — save what was done to fix it."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    # Team access check
    await require_team_access(doc.get("routed_to"), user, db)

    # Only the engineer who picked up the ticket can resolve it (admins can always resolve)
    if user["role"] == "engineer" and doc.get("picked_up_by") and doc["picked_up_by"] != user["email"]:
        raise HTTPException(403, f"Only {doc['picked_up_by']} can resolve this ticket (they picked it up)")

    if doc.get("status") == "closed":
        raise HTTPException(400, "Ticket is already closed")

    now = datetime.now(timezone.utc).isoformat()

    # ── Create resolution document ──
    try:
        from backend.services.orchestrator import get_embedding_model
        model = get_embedding_model()
        res_text = " ".join(resolve.resolution_steps)
        embedding = model.encode(res_text).tolist()
    except Exception:
        embedding = None

    # Determine effectiveness based on whether AI suggestion was used
    if resolve.used_ai_suggestion == "yes":
        effectiveness = 1.0  # confirmed AI suggestion works
    elif resolve.used_ai_suggestion == "partially":
        effectiveness = 0.85  # partially useful
    else:
        effectiveness = 0.90  # new fix, assume good

    res_doc = db.collection("resolutions").insert({
        "steps": resolve.resolution_steps,
        "effectiveness": effectiveness,
        "embedding": embedding,
    })

    # ── Create resolved_with edge ──
    try:
        db.collection("resolved_with").insert({
            "_from": f"tickets/{ticket_id}",
            "_to": f"resolutions/{res_doc['_key']}",
        })
    except Exception as exc:
        logger.warning("Failed to create resolved_with edge: %s", exc)

    # ── Create references edge (if runbook used) ──
    if resolve.used_runbook:
        try:
            db.collection("references").insert({
                "_from": f"resolutions/{res_doc['_key']}",
                "_to": f"runbooks/{resolve.used_runbook}",
            })
        except Exception as exc:
            logger.warning("Failed to create references edge: %s", exc)

    # ── Update AI suggestion effectiveness ──
    if resolve.used_ai_suggestion == "yes" and doc.get("suggested_resolution"):
        # Boost effectiveness of the resolution that was suggested
        try:
            query = """
            FOR res IN 1..1 OUTBOUND CONCAT("tickets/", @ticket_id) resolved_with
                LIMIT 1
                UPDATE res WITH { effectiveness: MIN(res.effectiveness + 0.05, 1.0) } IN resolutions
            """
            db.aql.execute(query, bind_vars={"ticket_id": ticket_id})
        except Exception as exc:
            logger.warning("Failed to boost resolution effectiveness: %s", exc)

    # ── Update ticket status ──
    collection.update({
        "_key": ticket_id,
        "status": "resolved",
        "resolved_at": now,
    })

    # ── Audit log ──
    try:
        db.collection("audit_log").insert({
            "ticket_id": ticket_id,
            "action": "resolved",
            "actor": user["email"],
            "old_value": {"status": doc.get("status")},
            "new_value": {
                "status": "resolved",
                "resolution_steps": resolve.resolution_steps,
                "used_ai_suggestion": resolve.used_ai_suggestion,
                "used_runbook": resolve.used_runbook,
            },
            "confidence_score": None,
            "reasoning": f"Resolved by {user['email']}. AI suggestion {'used' if resolve.used_ai_suggestion == 'yes' else 'not used'}.",
            "created_at": now,
        })
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)

    logger.info(
        "Ticket %s resolved by %s (AI suggestion: %s)",
        ticket_id, user["email"], resolve.used_ai_suggestion,
    )

    # Return updated ticket
    updated = collection.get(ticket_id)
    return _doc_to_response(updated)


@router.post("/{ticket_id}/feedback", status_code=201)
async def submit_feedback(
    ticket_id: str,
    feedback: TicketFeedback,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Submit feedback on AI classification/resolution suggestion."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    if feedback.rating not in ("helpful", "not_helpful"):
        raise HTTPException(400, "Rating must be 'helpful' or 'not_helpful'")

    now = datetime.now(timezone.utc).isoformat()

    try:
        db.collection("audit_log").insert({
            "ticket_id": ticket_id,
            "action": "feedback",
            "actor": user["email"],
            "old_value": None,
            "new_value": {
                "rating": feedback.rating,
                "comment": feedback.comment,
            },
            "confidence_score": doc.get("confidence_score"),
            "reasoning": f"AI suggestion rated '{feedback.rating}' by {user['email']}",
            "created_at": now,
        })
    except Exception as exc:
        logger.warning("Failed to write feedback: %s", exc)

    logger.info("Feedback on ticket %s: %s by %s", ticket_id, feedback.rating, user["email"])

    return {"status": "ok", "ticket_id": ticket_id, "rating": feedback.rating}


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Delete a ticket. Admin only."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    if not collection.has(ticket_id):
        raise HTTPException(404, "Ticket not found")

    # Clean up edges and audit log referencing this ticket
    ticket_full_id = f"tickets/{ticket_id}"
    for edge_col in ("assigned_to", "resolved_with"):
        try:
            db.aql.execute(
                f"FOR e IN {edge_col} FILTER e._from == @tid REMOVE e IN {edge_col}",
                bind_vars={"tid": ticket_full_id},
            )
        except Exception as exc:
            logger.warning("Failed to clean up %s edges: %s", edge_col, exc)

    try:
        db.aql.execute(
            "FOR a IN audit_log FILTER a.ticket_id == @tid REMOVE a IN audit_log",
            bind_vars={"tid": ticket_id},
        )
    except Exception as exc:
        logger.warning("Failed to clean up audit_log: %s", exc)

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
        picked_up_by=doc.get("picked_up_by"),
        created_at=doc.get("created_at"),
        resolved_at=doc.get("resolved_at"),
    )


def _team_key_to_name(db, team_key: str | None) -> str | None:
    """Resolve a team _key to its display name."""
    if not team_key:
        return None
    try:
        team = db.collection("teams").get(team_key)
        return team.get("name") if team else None
    except Exception:
        return None


def _lookup_team_key(db, team_name: str) -> str | None:
    """Find team _key from team name."""
    try:
        for doc in db.collection("teams").all():
            if doc.get("name") == team_name:
                return doc["_key"]
    except Exception:
        pass
    return None
