#!/usr/bin/env python3
"""
Create demo tickets for presentation.

Creates 6 user-submitted tickets across categories to trigger:
- Incident prediction (cluster: 3+ Infrastructure in 4 hours)
- Spike detection (5+ tickets in 1 hour)
- Dashboard with realistic data

Run before demo:
    source .venv/bin/activate
    OLLAMA_BASE_URL=http://localhost:11434 python scripts/create_demo_tickets.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arango import ArangoClient
from backend.core.config import settings
from backend.services.orchestrator import classify

DEMO_TICKETS = [
    {
        "title": "prod-app-01 server completely unresponsive",
        "description": "Production server prod-app-01 has been down since 5 AM. No SSH access, ping timing out. Monitoring shows server offline. Multiple services affected, customers reporting 503 errors. Need immediate investigation of hardware or VMware console.",
        "priority": "critical",
    },
    {
        "title": "Kubernetes node k8s-node-03 in NotReady state",
        "description": "Worker node k8s-node-03 has been NotReady for 30 minutes. Kubelet reporting CPU pressure at 98%. Several pods evicted. Kernel OOM killer triggered twice. Other nodes are healthy but this one is causing scheduling failures for critical workloads.",
        "priority": "high",
    },
    {
        "title": "Docker daemon failing to start on prod-web-02",
        "description": "Docker daemon on prod-web-02 crashes on startup with SIGSEGV. All containers on the host are down including nginx and the monitoring agent. Systemd journal shows repeated restart attempts hitting the rate limiter. Started after an interrupted OS patch yesterday.",
        "priority": "critical",
    },
    {
        "title": "PostgreSQL connection pool exhausted on prod-db-01",
        "description": "All 200 connections in the PostgreSQL connection pool on prod-db-01 are in use. New connections being refused with FATAL too many connections for role app_user. Payment service returning 500 errors. Suspect connection leak in the v2.4.1 deployment from yesterday.",
        "priority": "critical",
    },
    {
        "title": "SSL certificate expired on main load balancer",
        "description": "The wildcard SSL certificate for *.company.com expired 2 hours ago. All HTTPS traffic through the main load balancer is showing certificate warnings. Let's Encrypt auto-renewal failed because DNS challenge validation could not update the TXT record. Affecting all public-facing services.",
        "priority": "critical",
    },
    {
        "title": "Multiple users locked out of Active Directory after password policy change",
        "description": "Approximately 40 users have been locked out of Active Directory after the quarterly password rotation policy was enforced overnight. Users are unable to access email, VPN, JIRA, and Confluence. The new policy requires 16 characters minimum which many users were not prepared for. Help desk is overwhelmed with reset requests.",
        "priority": "high",
    },
]


async def main():
    print("=" * 60)
    print("DeskMind — Create Demo Tickets")
    print("=" * 60)
    print()

    client = ArangoClient(hosts=settings.ARANGO_URL)
    db = client.db(settings.ARANGO_DB, username=settings.ARANGO_USER, password=settings.ARANGO_PASSWORD)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    collection = db.collection("tickets")
    created = 0

    for i, ticket in enumerate(DEMO_TICKETS, 1):
        print(f"[{i}/{len(DEMO_TICKETS)}] Classifying: {ticket['title'][:50]}...")
        start = time.time()

        try:
            result = await classify(
                title=ticket["title"],
                description=ticket["description"],
                db=db,
                redis_client=None,
                skip_cache=True,
            )

            elapsed = time.time() - start

            # Build top3
            votes = result.get("classifier_votes", {})
            cat_scores = {}
            for clf, vote in votes.items():
                cat = vote.get("category")
                conf = vote.get("confidence", 0)
                if cat:
                    cat_scores[cat] = cat_scores.get(cat, 0) + conf
            top3 = sorted(
                [{"category": c, "score": round(s, 3)} for c, s in cat_scores.items()],
                key=lambda x: x["score"],
                reverse=True,
            )[:3]

            status = "routed" if result["confidence"] >= 0.70 else "escalated"

            doc = {
                "title": ticket["title"],
                "description": ticket["description"],
                "category": result["category"],
                "secondary_category": result.get("secondary_category"),
                "priority": ticket["priority"],
                "status": status,
                "confidence_score": result["confidence"],
                "ai_reasoning": result["reasoning"],
                "quality_score": result["quality_score"],
                "classifier_votes": result["classifier_votes"],
                "top3_predictions": top3,
                "submitted_by": "arif.asadullah@schwettmann.in",
                "routed_to": result["recommended_team"],
                "embedding": result["embedding"],
                "suggested_resolution": result["suggested_resolution"],
                "resolution_effectiveness": result["resolution_effectiveness"],
                "suggested_runbook": result["suggested_runbook"],
                "recommended_expert": result["recommended_expert"],
                "enrichment": result.get("enrichment"),
                "ai_generated_resolution": result.get("ai_generated_resolution"),
                "created_at": now,
                "resolved_at": None,
                "_source": "user",
            }

            inserted = collection.insert(doc)

            ai_gen = "YES" if result.get("ai_generated_resolution") else "no"
            print(f"         -> {result['category']} ({result['confidence']:.2f}) | {status} | AI-res={ai_gen} | {elapsed:.1f}s")
            print(f"         ID: {inserted['_key']}")
            created += 1

        except Exception as exc:
            print(f"         ERROR: {exc}")

        print()

    print("=" * 60)
    print(f"Created {created}/{len(DEMO_TICKETS)} demo tickets")
    print()
    print("Incident prediction should now show:")
    print("  - Cluster: 3+ Infrastructure tickets in 4 hours")
    print("  - Spike: 5+ total tickets in 1 hour")
    print()
    print("Refresh the dashboard to see the incident banner.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
