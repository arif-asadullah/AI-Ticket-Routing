"""Incident Prediction API — proactive pattern detection."""

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from backend.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

CACHE_KEY = "incidents:predictions"
CACHE_TTL = 60  # seconds

# Throttled auto-detection of repeated-issue clusters. Runs at most once per
# interval (instead of a separate scheduler/cron) so the repeated_issues
# collection stays fresh and check_repeated_match() can flag recurring tickets.
_last_repeated_scan = 0.0
REPEATED_SCAN_INTERVAL = 300  # seconds (5 min)


def _maybe_refresh_repeated_issues(db):
    """Run repeated-issue detection if it hasn't run recently (throttled)."""
    global _last_repeated_scan
    now_ts = time.time()
    if now_ts - _last_repeated_scan < REPEATED_SCAN_INTERVAL:
        return
    _last_repeated_scan = now_ts
    try:
        from backend.services.repeated_issues import detect_repeated_issues, save_repeated_issues
        clusters = detect_repeated_issues(db)
        save_repeated_issues(db, clusters)
        logger.info("Auto repeated-issue scan: %d cluster(s)", len(clusters))
    except Exception as exc:
        logger.warning("Auto repeated-issue detection failed: %s", exc)


@router.get("")
async def get_incidents(request: Request, user: dict = Depends(get_current_user)):
    """Get active incident predictions. Auto-scans recent tickets, cached for 60s."""
    db = getattr(request.app.state, "arango_db", None)
    redis_client = getattr(request.app.state, "redis", None)

    # Try cache first (per user role + team)
    cache_key = f"{CACHE_KEY}:{user.get('role', 'user')}:{user.get('team_key', 'all')}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    if db is None:
        return []

    # Keep the repeated-issue clusters fresh (throttled) so recurring tickets
    # get flagged with automation suggestions in the classification pipeline.
    _maybe_refresh_repeated_issues(db)

    incidents = []

    try:
        now = datetime.now(timezone.utc)

        # ── Cluster Detection: same category + team in last 4 hours ──
        since_4h = (now - timedelta(hours=4)).isoformat()
        cursor = db.aql.execute(
            """FOR t IN tickets
                FILTER t._source == "user"
                AND t.created_at >= @since
                AND t.status NOT IN ["resolved", "closed"]
                COLLECT team = t.routed_to, category = t.category
                WITH COUNT INTO cnt
                FILTER cnt >= 3
                SORT cnt DESC
                RETURN { team: team, category: category, count: cnt }""",
            bind_vars={"since": since_4h},
        )
        for cluster in cursor:
            severity = "critical" if cluster["count"] >= 5 else "high" if cluster["count"] >= 4 else "warning"
            incidents.append({
                "type": "cluster",
                "severity": severity,
                "title": f"Possible outage: {cluster['count']} {cluster['category']} tickets in 4 hours",
                "details": f"All routed to {cluster['team']}",
                "suggested_action": f"Check {cluster['category']} systems, contact {cluster['team']}",
                "count": cluster["count"],
                "category": cluster["category"],
                "team": cluster["team"],
            })

        # ── Trend Detection: this week vs last week by category ──
        this_week_start = (now - timedelta(days=7)).isoformat()
        last_week_start = (now - timedelta(days=14)).isoformat()

        cursor = db.aql.execute(
            """LET this_week = (
                FOR t IN tickets
                    FILTER t._source == "user" AND t.created_at >= @this_week
                    COLLECT cat = t.category WITH COUNT INTO cnt
                    RETURN { category: cat, count: cnt }
            )
            LET last_week = (
                FOR t IN tickets
                    FILTER t._source == "user"
                    AND t.created_at >= @last_week AND t.created_at < @this_week
                    COLLECT cat = t.category WITH COUNT INTO cnt
                    RETURN { category: cat, count: cnt }
            )
            RETURN { this_week, last_week }""",
            bind_vars={"this_week": this_week_start, "last_week": last_week_start},
        )
        trend_data = next(cursor, None)
        if trend_data:
            this_map = {r["category"]: r["count"] for r in trend_data["this_week"]}
            last_map = {r["category"]: r["count"] for r in trend_data["last_week"]}

            for cat, this_count in this_map.items():
                last_count = last_map.get(cat, 0)
                if last_count > 0 and this_count >= last_count * 1.5 and this_count >= 3:
                    pct = round((this_count / last_count - 1) * 100)
                    incidents.append({
                        "type": "trend",
                        "severity": "warning",
                        "title": f"{cat} tickets trending up: {this_count} this week vs {last_count} last week",
                        "details": f"{pct}% increase from last week",
                        "suggested_action": f"Review recent {cat} changes and deployments",
                        "count": this_count,
                        "category": cat,
                    })

        # ── Recent spike: 5+ tickets in last hour ──
        since_1h = (now - timedelta(hours=1)).isoformat()
        cursor = db.aql.execute(
            """FOR t IN tickets
                FILTER t._source == "user" AND t.created_at >= @since
                AND t.status NOT IN ["resolved", "closed"]
                COLLECT WITH COUNT INTO cnt
                RETURN cnt""",
            bind_vars={"since": since_1h},
        )
        recent_count = next(cursor, 0)
        if recent_count >= 5:
            incidents.append({
                "type": "spike",
                "severity": "critical",
                "title": f"Ticket spike: {recent_count} new tickets in the last hour",
                "details": "Unusual volume detected",
                "suggested_action": "Check for widespread outage or incident",
                "count": recent_count,
            })

    except Exception as exc:
        logger.warning("Incident scan failed: %s", exc)

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "warning": 2}
    incidents.sort(key=lambda x: severity_order.get(x.get("severity", "warning"), 3))

    # Filter by user role — engineers only see their team's incidents
    if user.get("role") == "engineer":
        # Resolve team name from team_key
        team_name = None
        team_key = user.get("team_key")
        if team_key and db:
            try:
                team_doc = db.collection("teams").get(team_key)
                if team_doc:
                    team_name = team_doc.get("name")
            except Exception:
                pass
        if team_name:
            incidents = [i for i in incidents if i.get("team") == team_name or i.get("type") == "spike"]
        else:
            incidents = [i for i in incidents if i.get("type") == "spike"]
    elif user.get("role") == "user":
        # Regular users only see general spike alerts
        incidents = [i for i in incidents if i.get("type") == "spike"]

    # Cache per user role (admin sees all, others filtered)
    cache_key = f"{CACHE_KEY}:{user.get('role', 'user')}:{user.get('team_key', 'all')}"
    if redis_client:
        try:
            await redis_client.set(cache_key, json.dumps(incidents), ex=CACHE_TTL)
        except Exception:
            pass

    return incidents
