"""Tickets API — CRUD backed by ArangoDB with 4-classifier AI routing."""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import (
    get_current_user,
    require_admin,
    require_any_authenticated,
    require_engineer_or_admin,
    require_team_access,
)
from backend.schemas.ticket import TicketCreate, TicketEnrich, TicketFeedback, TicketOverride, TicketResolve, TicketResponse, TicketStatusUpdate
from backend.services.orchestrator import classify
from backend.services.router import cancel_sla_timer, get_breached_tickets, get_top3_predictions, start_sla_timer
from backend.services.socketio_manager import emit_ticket_event

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

    # ── Combine OCR text from attachments with description ──
    classify_description = ticket.description
    attachments_data = []
    if ticket.attachment_ids:
        import json as _json
        for file_id in ticket.attachment_ids:
            meta_path = os.path.join(os.path.dirname(__file__), "..", "uploads", f"{file_id}.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = _json.load(f)
                attachments_data.append(meta)
                ocr = meta.get("ocr_result", {})
                if ocr.get("raw_text"):
                    classify_description += f"\n\n[Screenshot Analysis]\n"
                    classify_description += f"Type: {ocr.get('screenshot_type_label', 'Screenshot')}\n"
                    classify_description += f"Extracted text: {ocr['raw_text'][:500]}\n"
                    if ocr.get("summary"):
                        classify_description += f"Summary: {ocr['summary']}"

    # ── Run the 4-classifier pipeline ──
    try:
        result = await classify(
            title=ticket.title,
            description=classify_description,
            db=db,
            redis_client=redis_client,
            user_email=user["email"],
        )
    except Exception as exc:
        logger.error("Classification pipeline failed: %s", exc)
        raise HTTPException(500, "Classification failed. Please try again.")

    # Determine status based on confidence and degradation level
    if result["degradation_level"] <= 1 and result["confidence"] < 0.50:
        status = "pending_human"
    elif result["confidence"] >= 0.70:
        status = "routed"
    else:
        status = "escalated"

    now = datetime.now(timezone.utc).isoformat()

    # ── Compute SLA deadline and top-3 predictions ──
    from backend.services.router import SLA_HOURS, get_sla_deadline
    sla_deadline = None
    sla_hours = SLA_HOURS.get(result["priority"], 8)
    top3 = get_top3_predictions(result["classifier_votes"])

    if status == "routed":
        sla_deadline, _ = get_sla_deadline(result["priority"], now)

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
        "top3_predictions": top3,
        "submitted_by": user["email"],
        "routed_to": result["recommended_team"],
        "embedding": result["embedding"],
        "suggested_resolution": result["suggested_resolution"],
        "resolution_effectiveness": result["resolution_effectiveness"],
        "suggested_runbook": result["suggested_runbook"],
        "recommended_expert": result["recommended_expert"],
        "sla_deadline": sla_deadline,
        "sla_hours": sla_hours,
        "enrichment": result.get("enrichment"),
        "ai_generated_resolution": result.get("ai_generated_resolution"),
        "attachments": attachments_data if attachments_data else None,
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

    # ── Start SLA timer in Redis (routed tickets only) ──
    if status == "routed" and result["recommended_team"]:
        await start_sla_timer(redis_client, ticket_key, result["priority"], result["recommended_team"], now)

    logger.info(
        "Ticket %s: %s → %s (%.1f%% confidence, %s, level=%d, %dms)",
        ticket_key, result["category"], result["recommended_team"],
        result["confidence"] * 100, result["agreement"],
        result["degradation_level"], result["processing_time_ms"],
    )

    await emit_ticket_event("ticket:created", {"id": ticket_key, "title": ticket.title, "status": status, "category": result["category"], "routed_to": result["recommended_team"], "actor": user["email"]})

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
        top3_predictions=top3,
        sla_deadline=sla_deadline,
        sla_hours=sla_hours,
        enrichment=result.get("enrichment"),
        ai_generated_resolution=result.get("ai_generated_resolution"),
        attachments=attachments_data if attachments_data else None,
        created_at=now,
        resolved_at=None,
    )


@router.get("/sla-breached")
async def sla_breached(request: Request, user: dict = Depends(require_engineer_or_admin)):
    """Get tickets that have breached their SLA deadline."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")
    redis_client = getattr(request.app.state, "redis", None)
    tickets = await get_breached_tickets(db, redis_client)
    return tickets


@router.post("/{ticket_id}/enrich", response_model=TicketResponse)
async def enrich_ticket(
    ticket_id: str,
    body: TicketEnrich,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """Enrich a vague ticket with additional details, then re-classify."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")
    redis_client = getattr(request.app.state, "redis", None)

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    # Build enriched description
    from backend.services.enrichment_agent import build_enriched_description
    enriched_desc = build_enriched_description(doc.get("description", ""), body.answers)

    # Re-classify with enriched text (skip cache, pure 4-classifier ensemble)
    try:
        new_result = await classify(
            title=doc.get("title", ""),
            description=enriched_desc,
            db=db,
            redis_client=redis_client,
            user_email=user["email"],
            skip_cache=True,
        )
    except Exception as exc:
        logger.error("Re-classification failed: %s", exc)
        raise HTTPException(500, "Re-classification failed")

    # Upgrade priority if impact is "Production down"
    impact_answer = body.answers.get("impact", "").strip().lower()
    if impact_answer == "production down" and new_result["priority"] != "critical":
        new_result["priority"] = "critical"

    # Determine new status
    old_confidence = doc.get("confidence_score", 0)
    new_confidence = new_result["confidence"]
    if new_result["degradation_level"] <= 1 and new_confidence < 0.50:
        new_status = "pending_human"
    elif new_confidence >= 0.70:
        new_status = "routed"
    else:
        new_status = "escalated"

    now = datetime.now(timezone.utc).isoformat()

    # Update ticket
    update_fields = {
        "_key": ticket_id,
        "description": enriched_desc,
        "category": new_result["category"],
        "secondary_category": new_result["secondary_category"],
        "priority": new_result["priority"],
        "status": new_status,
        "confidence_score": new_confidence,
        "ai_reasoning": new_result["reasoning"],
        "quality_score": new_result["quality_score"],
        "classifier_votes": new_result["classifier_votes"],
        "routed_to": new_result["recommended_team"],
        "suggested_resolution": new_result["suggested_resolution"],
        "recommended_expert": new_result["recommended_expert"],
        "ai_generated_resolution": new_result.get("ai_generated_resolution"),
        "enrichment": {
            "answers": body.answers,
            "enriched_at": now,
            "enriched_by": user["email"],
            "confidence_before": old_confidence,
            "confidence_after": new_confidence,
            "improved": new_confidence > old_confidence,
        },
    }
    collection.update(update_fields)

    # Update graph edges if team changed
    if new_result["recommended_team"] and new_result["recommended_team"] != doc.get("routed_to"):
        try:
            team_key = _lookup_team_key(db, new_result["recommended_team"])
            if team_key:
                db.aql.execute(
                    "FOR e IN assigned_to FILTER e._from == CONCAT('tickets/', @tid) REMOVE e IN assigned_to",
                    bind_vars={"tid": ticket_id},
                )
                db.collection("assigned_to").insert({
                    "_from": f"tickets/{ticket_id}",
                    "_to": f"teams/{team_key}",
                })
        except Exception as exc:
            logger.warning("Failed to update edges: %s", exc)

    # Start SLA if now routed
    if new_status == "routed" and new_result["recommended_team"]:
        await start_sla_timer(redis_client, ticket_id, new_result["priority"], new_result["recommended_team"], now)

    # Audit log
    try:
        db.collection("audit_log").insert({
            "ticket_id": ticket_id,
            "action": "enriched",
            "actor": user["email"],
            "old_value": {"category": doc.get("category"), "quality": doc.get("quality_score")},
            "new_value": {"category": new_result["category"], "quality": new_result["quality_score"], "answers": body.answers},
            "confidence_score": new_confidence,
            "confidence_signals": {
                "llm": new_result["classifier_votes"].get("llm", {}).get("confidence"),
                "knn": new_result["classifier_votes"].get("knn", {}).get("confidence"),
                "centroid": new_result["classifier_votes"].get("centroid", {}).get("confidence"),
                "keyword": new_result["classifier_votes"].get("keyword", {}).get("confidence"),
            },
            "reasoning": f"Enriched with additional details. Quality: {doc.get('quality_score', 'LOW')} → {new_result['quality_score']}. Category: {new_result['category']}.",
            "created_at": now,
        })
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)

    logger.info("Ticket %s enriched: %.0f%% → %.0f%% by %s", ticket_id, old_confidence * 100, new_confidence * 100, user["email"])

    await emit_ticket_event("ticket:updated", {
        "id": ticket_id, "status": new_status,
        "category": new_result["category"], "enriched": True,
        "actor": user["email"], "title": doc.get("title", ""),
    })

    updated = collection.get(ticket_id)
    return _doc_to_response(updated)


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

    valid_statuses = {"in_progress", "escalated", "routed", "pending_human"}
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
    await emit_ticket_event("ticket:updated", {"id": ticket_id, "status": update.status, "actor": user["email"], "title": updated.get("title", "")})
    return _doc_to_response(updated)


@router.put("/{ticket_id}/override", response_model=TicketResponse)
async def override_classification(
    ticket_id: str,
    body: TicketOverride,
    request: Request,
    user: dict = Depends(require_engineer_or_admin),
):
    """Override AI classification — analyst manually re-categorises a ticket."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    await require_team_access(doc.get("routed_to"), user, db)

    if doc.get("status") in ("resolved", "closed"):
        raise HTTPException(400, "Cannot override resolved/closed ticket")

    now = datetime.now(timezone.utc).isoformat()
    old_category = doc.get("category")
    old_priority = doc.get("priority")
    old_team = doc.get("routed_to")

    # Look up the team for the new category via routing_rules → teams
    new_team = None
    try:
        cursor = db.aql.execute(
            """FOR r IN routing_rules FILTER r.category == @cat AND r.is_active == true LIMIT 1
               LET team = DOCUMENT(CONCAT("teams/", r.target_team))
               RETURN team.name""",
            bind_vars={"cat": body.category},
        )
        new_team = next(cursor, None)
    except Exception as exc:
        logger.warning("Failed to find routing rule for %s: %s", body.category, exc)

    update_fields = {
        "_key": ticket_id,
        "category": body.category,
        "override": {
            "overridden_by": user["email"],
            "reason": body.reason,
            "original_category": old_category,
            "original_confidence": doc.get("confidence_score"),
            "overridden_at": now,
        },
    }

    if body.priority:
        update_fields["priority"] = body.priority

    if new_team:
        update_fields["routed_to"] = new_team
        # Update assigned_to edge
        try:
            team_key = _lookup_team_key(db, new_team)
            if team_key:
                db.aql.execute(
                    "FOR e IN assigned_to FILTER e._from == CONCAT('tickets/', @tid) REMOVE e IN assigned_to",
                    bind_vars={"tid": ticket_id},
                )
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
            "action": "override",
            "actor": user["email"],
            "old_value": {"category": old_category, "priority": old_priority, "team": old_team},
            "new_value": {"category": body.category, "priority": body.priority or old_priority, "team": new_team or old_team},
            "confidence_score": doc.get("confidence_score"),
            "reasoning": body.reason,
            "created_at": now,
        })
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)

    # ── Record correction for continuous learning ──
    try:
        from backend.services.corrections import record_correction
        record_correction(
            db=db, ticket_id=ticket_id, ticket_doc=doc,
            new_category=body.category, new_priority=body.priority,
            corrected_by=user["email"], corrector_role=user["role"],
            reason=body.reason,
        )
    except Exception as exc:
        logger.warning("Failed to record correction: %s", exc)

    # ── Invalidate cache so stale classification isn't served ──
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        try:
            from backend.services.cache import invalidate_for_correction
            await invalidate_for_correction(redis_client, doc.get("title", ""), doc.get("description", ""))
        except Exception as exc:
            logger.warning("Failed to invalidate cache: %s", exc)

    logger.info(
        "Ticket %s: override %s → %s by %s (reason: %s)",
        ticket_id, old_category, body.category, user["email"], body.reason,
    )

    updated = collection.get(ticket_id)
    await emit_ticket_event("ticket:updated", {
        "id": ticket_id, "category": body.category,
        "routed_to": new_team or old_team, "override": True,
        "actor": user["email"], "title": updated.get("title", ""),
    })
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
        "ticket_id": ticket_id,
        "steps": resolve.resolution_steps,
        "effectiveness": effectiveness,
        "embedding": embedding,
        "verified": False,
        "created_at": now,
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

    # ── Cancel SLA timer ──
    redis_client = getattr(request.app.state, "redis", None)
    await cancel_sla_timer(redis_client, ticket_id)

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
    await emit_ticket_event("ticket:resolved", {"id": ticket_id, "status": "resolved", "actor": user["email"], "title": updated.get("title", "")})
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

    # ── Save feedback rating on ticket ──
    collection.update({"_key": ticket_id, "feedback_rating": feedback.rating})

    # ── Quality gate: update resolution based on feedback ──
    try:
        if feedback.rating == "helpful":
            # Verify resolution + boost effectiveness
            db.aql.execute(
                """FOR res IN 1..1 OUTBOUND CONCAT("tickets/", @tid) resolved_with
                   LET new_eff = res.effectiveness + 0.1
                   UPDATE res WITH { verified: true, effectiveness: new_eff > 1.0 ? 1.0 : new_eff } IN resolutions""",
                bind_vars={"tid": ticket_id},
            )
        elif feedback.rating == "not_helpful":
            # Lower effectiveness, keep unverified
            db.aql.execute(
                """FOR res IN 1..1 OUTBOUND CONCAT("tickets/", @tid) resolved_with
                   LET new_eff = res.effectiveness - 0.2
                   UPDATE res WITH { verified: false, effectiveness: new_eff < 0.3 ? 0.3 : new_eff } IN resolutions""",
                bind_vars={"tid": ticket_id},
            )
    except Exception as exc:
        logger.warning("Failed to update resolution quality: %s", exc)

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
    await emit_ticket_event("ticket:deleted", {"id": ticket_id, "actor": admin["email"]})


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
        override=doc.get("override"),
        top3_predictions=doc.get("top3_predictions"),
        sla_deadline=doc.get("sla_deadline"),
        sla_hours=doc.get("sla_hours"),
        enrichment=doc.get("enrichment"),
        ai_generated_resolution=doc.get("ai_generated_resolution"),
        attachments=doc.get("attachments"),
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
