"""Re-gate stored runbook suggestions on existing tickets.

Tickets classified before the find_runbook relevance gate (or before the
resolution-steps leak fix) may store an irrelevant suggested_runbook. This
re-runs the current gate over every ticket that has one and clears/updates
any that no longer pass.

Run inside the backend container:
    docker compose exec backend python scripts/regate_runbooks.py [--apply]
Without --apply it reports what would change (dry run).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.database import connect_arango
from backend.services.orchestrator import find_runbook


def main():
    apply = "--apply" in sys.argv
    db = connect_arango()
    if db is None:
        sys.exit("Could not connect to ArangoDB")
    tickets = db.collection("tickets")

    cursor = db.aql.execute("""
        FOR t IN tickets
            FILTER t.suggested_runbook != null
            RETURN { key: t._key, title: t.title, description: t.description,
                     category: t.category, runbook: t.suggested_runbook }
    """)
    rows = list(cursor)
    print(f"{len(rows)} tickets have a stored suggested_runbook")

    changed = 0
    for r in rows:
        regated = find_runbook(db, r["category"], r["title"], r["description"])
        if regated != r["runbook"]:
            changed += 1
            print(f"  {r['key']} | {(r['title'] or '')[:50]}")
            print(f"      stored: {r['runbook']}")
            print(f"      regate: {regated}")
            if apply:
                tickets.update({"_key": r["key"], "suggested_runbook": regated})

    print(f"\n{changed} ticket(s) {'updated' if apply else 'would change (dry run — use --apply)'}")


if __name__ == "__main__":
    main()
