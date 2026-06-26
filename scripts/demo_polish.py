"""
Demo data polish — run SHORTLY BEFORE a live demo.

Idempotent. Two jobs:

1. Realistic resolution times — resolves a set of tickets with believable
   durations (critical ~1-2h, high ~3-6h, medium ~1 day) so the dashboard's
   "Avg Resolution" shows a credible ~4-6h instead of a noisy 60h outlier.

2. Stage a live incident — re-timestamps a cluster of Database tickets to the
   last ~45 minutes (same team, status 'routed') so the Incident Agent fires a
   CRITICAL cluster ("Possible outage: N Database tickets in 4 hours") AND a
   CRITICAL spike ("N new tickets in the last hour").

   WARNING: Incident detection is TIME-RELATIVE (last 1-4 hours). Run this within
   ~30 minutes of the demo so the incident is fresh. Re-run any time — it's safe.

This only touches synthetic demo tickets (timestamps/status). It does NOT touch
the 94.1% benchmark, training data, or any committed code. Re-seed to reset.

Usage (inside the backend container):
    docker compose exec -T backend python scripts/demo_polish.py
"""

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arango import ArangoClient

from backend.core.config import settings

# How many Database tickets to stage as the live incident (>=5 -> CRITICAL).
INCIDENT_COUNT = 5
INCIDENT_CATEGORY = "Database"
# How many tickets to resolve with realistic durations (for Avg Resolution).
RESOLVE_COUNT = 16
# Realistic resolution duration ranges (hours) by priority.
DURATION_HOURS = {
    "critical": (1, 2),
    "high": (3, 6),
    "medium": (18, 30),
    "low": (24, 48),
}


def _db():
    return ArangoClient(hosts=settings.ARANGO_URL).db(
        settings.ARANGO_DB, username=settings.ARANGO_USER, password=settings.ARANGO_PASSWORD
    )


def main():
    random.seed(42)  # deterministic so re-runs are stable
    db = _db()
    tickets = db.collection("tickets")
    now = datetime.now(timezone.utc)

    # Deterministic ordering so selection is stable across runs.
    user_tix = list(db.aql.execute(
        """FOR t IN tickets FILTER t._source == "user"
            SORT t._key
            RETURN {k: t._key, cat: t.category, pri: t.priority, rt: t.routed_to, created: t.created_at}"""
    ))

    # -- 1. Stage the incident: first N Database tickets -> recent + routed --
    incident_keys = [t["k"] for t in user_tix if t["cat"] == INCIDENT_CATEGORY][:INCIDENT_COUNT]
    for key in incident_keys:
        created = (now - timedelta(minutes=random.randint(5, 45))).isoformat()
        tickets.update({
            "_key": key,
            "status": "routed",
            "created_at": created,
            "resolved_at": None,
        })
    print(f"Incident staged: {len(incident_keys)} {INCIDENT_CATEGORY} tickets in the last hour "
          f"(-> CRITICAL cluster + CRITICAL spike)")

    # -- 2. Resolve a set with realistic durations (skip the incident tickets) --
    incident_set = set(incident_keys)
    # Prefer critical/high so the average stays demo-credible.
    resolvable = [t for t in user_tix if t["k"] not in incident_set and t["pri"] in ("critical", "high", "medium")]
    resolvable.sort(key=lambda t: {"critical": 0, "high": 1, "medium": 2}.get(t["pri"], 3))
    chosen = resolvable[:RESOLVE_COUNT]

    durations = []
    for t in chosen:
        lo, hi = DURATION_HOURS.get(t["pri"], (3, 6))
        dur_h = random.uniform(lo, hi)
        # Resolved a little while ago; created = resolved - duration (both in the past).
        resolved_at = now - timedelta(minutes=random.randint(10, 240))
        created_at = resolved_at - timedelta(hours=dur_h)
        tickets.update({
            "_key": t["k"],
            "status": "resolved",
            "created_at": created_at.isoformat(),
            "resolved_at": resolved_at.isoformat(),
        })
        durations.append(dur_h)

    if durations:
        avg = sum(durations) / len(durations)
        print(f"Resolved {len(durations)} tickets with realistic durations - "
              f"avg ~ {avg:.1f}h (min {min(durations):.1f}h, max {max(durations):.1f}h)")

    print("\nDone. Open the dashboard within ~30 min:")
    print("  - Domain Dashboard -> 'Avg Resolution' now reads a credible few hours")
    print("  - Incident Agent -> CRITICAL cluster + spike on Database")
    print("  (The incidents API caches for 60s - wait up to a minute if not shown yet.)")


if __name__ == "__main__":
    main()
