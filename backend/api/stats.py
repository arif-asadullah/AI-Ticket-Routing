"""Stats API — aggregated metrics and ticket audit timeline."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _get_db(request: Request):
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")
    return db


def _team_key_to_name(db, team_key: str | None) -> str | None:
    if not team_key:
        return None
    try:
        team = db.collection("teams").get(team_key)
        return team.get("name") if team else None
    except Exception:
        return None


@router.get("")
async def get_stats(request: Request, user: dict = Depends(get_current_user)):
    """Get aggregated stats. Admin sees global, engineer sees team-scoped."""
    db = _get_db(request)
    redis_client = getattr(request.app.state, "redis", None)

    # Determine scope
    team_filter = ""
    bind_vars = {}
    if user["role"] == "engineer" and user.get("team_key"):
        team_name = _team_key_to_name(db, user["team_key"])
        if team_name:
            team_filter = 'FILTER t.routed_to == @team_name'
            bind_vars["team_name"] = team_name

    # Check Redis cache
    cache_key = f"stats:{user.get('team_key', 'global')}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # Single optimized AQL query
    query = f"""
    LET user_tickets = (
        FOR t IN tickets
            FILTER t._source == "user"
            {team_filter}
            RETURN t
    )

    LET all_tickets = (
        FOR t IN tickets
            FILTER t._source == "user"
            {team_filter}
            RETURN t
    )

    LET by_category = (
        FOR t IN all_tickets
            COLLECT cat = t.category WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN {{ category: cat, count: cnt }}
    )

    LET by_status = (
        FOR t IN user_tickets
            COLLECT st = t.status WITH COUNT INTO cnt
            RETURN {{ status: st, count: cnt }}
    )

    LET by_priority = (
        FOR t IN user_tickets
            COLLECT pri = t.priority WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN {{ priority: pri, count: cnt }}
    )

    LET total_user = LENGTH(user_tickets)

    LET avg_confidence = AVERAGE(
        FOR t IN user_tickets
            FILTER t.confidence_score != null
            RETURN t.confidence_score
    )

    LET confidence_by_category = (
        FOR t IN all_tickets
            FILTER t.confidence_score != null
            COLLECT cat = t.category
            AGGREGATE avgConf = AVERAGE(t.confidence_score)
            RETURN {{ category: cat, avg_confidence: ROUND(avgConf * 1000) / 1000 }}
    )

    LET escalated_count = LENGTH(
        FOR t IN user_tickets FILTER t.status == "escalated" RETURN 1
    )

    LET resolved_tickets = (
        FOR t IN user_tickets
            FILTER t.status == "resolved"
            AND t.resolved_at != null
            AND t.created_at != null
            RETURN DATE_DIFF(t.created_at, t.resolved_at, "minute")
    )
    LET avg_resolution_minutes = AVERAGE(resolved_tickets)

    LET daily_trend = (
        FOR t IN user_tickets
            FILTER t.created_at != null
            COLLECT day = SUBSTRING(t.created_at, 0, 10)
            WITH COUNT INTO cnt
            SORT day DESC
            LIMIT 90
            SORT day ASC
            RETURN {{ date: day, count: cnt }}
    )

    LET top_teams = (
        FOR t IN all_tickets
            FILTER t.routed_to != null
            COLLECT team = t.routed_to WITH COUNT INTO cnt
            SORT cnt DESC
            LIMIT 10
            RETURN {{ team: team, count: cnt }}
    )

    LET feedback_entries = (
        FOR a IN audit_log
            FILTER a.action == "feedback"
            LIMIT 10000
            RETURN a.new_value.rating
    )
    LET helpful_count = LENGTH(
        FOR r IN feedback_entries FILTER r == "helpful" RETURN 1
    )
    LET not_helpful_count = LENGTH(
        FOR r IN feedback_entries FILTER r == "not_helpful" RETURN 1
    )

    LET classifier_votes_data = (
        FOR t IN user_tickets
            FILTER t.classifier_votes != null
            LET votes = t.classifier_votes
            LET cats = REMOVE_VALUE([
                votes.llm.category,
                votes.knn.category,
                votes.centroid.category,
                votes.keyword.category
            ], null)
            RETURN LENGTH(UNIQUE(cats)) == 1 AND LENGTH(cats) >= 3
    )
    LET all_agree_count = LENGTH(
        FOR a IN classifier_votes_data FILTER a == true RETURN 1
    )
    LET total_with_votes = LENGTH(classifier_votes_data)

    RETURN {{
        total: total_user,
        total_all: LENGTH(all_tickets),
        by_category: by_category,
        by_status: by_status,
        by_priority: by_priority,
        avg_confidence: ROUND((avg_confidence OR 0) * 1000) / 1000,
        confidence_by_category: confidence_by_category,
        escalation_rate: total_user > 0 ? ROUND(escalated_count * 1000 / total_user) / 1000 : 0,
        avg_resolution_minutes: ROUND((avg_resolution_minutes OR 0) * 10) / 10,
        daily_trend: daily_trend,
        top_teams: top_teams,
        feedback: {{ helpful: helpful_count, not_helpful: not_helpful_count }},
        classifier_agreement: total_with_votes > 0 ? ROUND(all_agree_count * 1000 / total_with_votes) / 1000 : 0
    }}
    """

    try:
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        result = next(cursor, {})
    except Exception as exc:
        logger.error("Stats query failed: %s", exc)
        raise HTTPException(500, "Stats query failed. Please try again.")

    # Cache in Redis (60s TTL)
    if redis_client:
        try:
            await redis_client.set(cache_key, json.dumps(result), ex=60)
        except Exception:
            pass

    return result


@router.get("/tickets/{ticket_id}/timeline")
async def get_ticket_timeline(
    ticket_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Get audit trail for a specific ticket."""
    db = _get_db(request)

    # Verify ticket exists
    doc = db.collection("tickets").get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    # Team access check for engineers
    if user["role"] == "engineer":
        team_name = _team_key_to_name(db, user.get("team_key"))
        if doc.get("routed_to") != team_name:
            raise HTTPException(403, "This ticket is not assigned to your team")

    query = """
    FOR a IN audit_log
        FILTER a.ticket_id == @ticket_id
        SORT a.created_at ASC
        RETURN {
            action: a.action,
            actor: a.actor,
            old_value: a.old_value,
            new_value: a.new_value,
            confidence_score: a.confidence_score,
            confidence_signals: a.confidence_signals,
            reasoning: a.reasoning,
            created_at: a.created_at
        }
    """

    try:
        cursor = db.aql.execute(query, bind_vars={"ticket_id": ticket_id})
        return list(cursor)
    except Exception as exc:
        logger.error("Timeline query failed: %s", exc)
        raise HTTPException(500, "Timeline query failed. Please try again.")
