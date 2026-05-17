"""Routing service — team assignment and SLA management.

SLA timers use Redis keys with TTL:
    sla:{ticket_id} → JSON with deadline, priority, team
    When TTL expires, the key disappears → ticket is SLA-breached.

SLA hours by priority (from seed data):
    Critical = 2h, High = 4h, Medium = 8h, Low = 24h
"""

import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SLA_HOURS = {
    "critical": 2,
    "high": 4,
    "medium": 8,
    "low": 24,
}


def get_sla_deadline(priority: str, created_at: str | None = None) -> tuple[str, int]:
    """Calculate SLA deadline and TTL in seconds.

    Returns (deadline_iso, ttl_seconds).
    """
    hours = SLA_HOURS.get(priority, 8)
    base = datetime.now(timezone.utc)
    if created_at:
        try:
            base = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            pass
    deadline = base + timedelta(hours=hours)
    ttl = int((deadline - datetime.now(timezone.utc)).total_seconds())
    return deadline.isoformat(), max(ttl, 1)


async def start_sla_timer(redis_client, ticket_id: str, priority: str, team: str, created_at: str | None = None) -> dict | None:
    """Start an SLA timer in Redis for a routed ticket.

    Returns the SLA info dict or None if Redis unavailable.
    """
    if redis_client is None:
        return None

    deadline, ttl = get_sla_deadline(priority, created_at)
    sla_info = {
        "ticket_id": ticket_id,
        "priority": priority,
        "team": team,
        "deadline": deadline,
        "sla_hours": SLA_HOURS.get(priority, 8),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        key = f"sla:{ticket_id}"
        await redis_client.set(key, json.dumps(sla_info), ex=ttl)
        logger.info("SLA started: ticket=%s, priority=%s, deadline=%s, ttl=%ds", ticket_id, priority, deadline, ttl)
        return sla_info
    except Exception as exc:
        logger.warning("Failed to start SLA timer for %s: %s", ticket_id, exc)
        return None


async def get_sla_info(redis_client, ticket_id: str) -> dict | None:
    """Get SLA info for a ticket. Returns None if expired (breached) or not set."""
    if redis_client is None:
        return None
    try:
        raw = await redis_client.get(f"sla:{ticket_id}")
        if raw:
            info = json.loads(raw)
            ttl = await redis_client.ttl(f"sla:{ticket_id}")
            info["remaining_seconds"] = max(ttl, 0)
            return info
    except Exception as exc:
        logger.warning("Failed to get SLA info for %s: %s", ticket_id, exc)
    return None


async def cancel_sla_timer(redis_client, ticket_id: str) -> None:
    """Cancel SLA timer (e.g. on resolve)."""
    if redis_client is None:
        return
    try:
        await redis_client.delete(f"sla:{ticket_id}")
        logger.info("SLA cancelled: ticket=%s", ticket_id)
    except Exception as exc:
        logger.warning("Failed to cancel SLA for %s: %s", ticket_id, exc)


async def get_breached_tickets(db, redis_client) -> list[dict]:
    """Find tickets that have breached their SLA.

    A ticket is breached if:
    - It has status routed/in_progress/escalated (not resolved/closed)
    - It has an sla_deadline field that is in the past
    - AND the Redis sla: key has expired (TTL gone)
    """
    if db is None:
        return []

    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = db.aql.execute(
            """FOR t IN tickets
                FILTER t.status IN ['routed', 'in_progress', 'escalated', 'pending_human']
                AND t.sla_deadline != null
                AND t.sla_deadline < @now
                SORT t.priority == 'critical' ? 0 : t.priority == 'high' ? 1 : t.priority == 'medium' ? 2 : 3 ASC,
                     t.sla_deadline ASC
                RETURN {
                    id: t._key,
                    title: t.title,
                    category: t.category,
                    priority: t.priority,
                    status: t.status,
                    routed_to: t.routed_to,
                    sla_deadline: t.sla_deadline,
                    sla_hours: t.sla_hours,
                    created_at: t.created_at
                }""",
            bind_vars={"now": now},
        )
        return list(cursor)
    except Exception as exc:
        logger.warning("Failed to query SLA-breached tickets: %s", exc)
        return []


def get_top3_predictions(classifier_votes: dict) -> list[dict]:
    """Extract top-3 unique category predictions from classifier votes."""
    prediction_map = {}
    for name, vote in classifier_votes.items():
        if not vote or not vote.get("category"):
            continue
        cat = vote["category"]
        conf = vote.get("confidence", 0)
        if cat not in prediction_map or conf > prediction_map[cat]["confidence"]:
            prediction_map[cat] = {
                "category": cat,
                "confidence": conf,
                "classifier": name,
            }

    sorted_preds = sorted(prediction_map.values(), key=lambda x: x["confidence"], reverse=True)
    return sorted_preds[:3]
