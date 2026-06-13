"""Backfill engineer login accounts on the live DB (non-destructive).

Adds one engineer-role login per engineer in the `engineers` collection — all
sharing the password "eng123" — assigned to the engineer's team via the
member_of edge. Also normalises engineer emails (and team escalation contacts)
to the @schwettmann.in domain. The admin account is never touched.

This avoids a full `seed_db.py` run (which rewrites tickets and resets the admin
password). Re-runnable / idempotent.

Run inside the backend container:
    docker compose exec backend python scripts/add_engineer_users.py [--apply]
Without --apply it reports what would change (dry run).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt

from backend.services.database import connect_arango

ENG_PASSWORD = "eng123"
NEW_DOMAIN = "@schwettmann.in"
OLD_DOMAIN = "@company.com"


def to_new_domain(email: str) -> str:
    if email and email.endswith(OLD_DOMAIN):
        return email[: -len(OLD_DOMAIN)] + NEW_DOMAIN
    return email


def main():
    apply = "--apply" in sys.argv
    db = connect_arango()
    if db is None:
        sys.exit("Could not connect to ArangoDB")

    engineers = list(db.collection("engineers").all())
    # engineer_key -> team_key via member_of edges
    eng_team = {}
    for e in db.collection("member_of").all():
        try:
            eng_team[e["_from"].split("/", 1)[1]] = e["_to"].split("/", 1)[1]
        except (KeyError, IndexError):
            continue

    users = db.collection("users")
    eng_col = db.collection("engineers")
    pw_hash = bcrypt.hashpw(ENG_PASSWORD.encode(), bcrypt.gensalt()).decode()

    print(f"{len(engineers)} engineers found\n")
    created = 0
    for eng in sorted(engineers, key=lambda x: x["_key"]):
        old_email = eng.get("email") or ""
        email = to_new_domain(old_email)
        team_key = eng_team.get(eng["_key"])
        first, _, last = (eng.get("name") or "").strip().partition(" ")
        print(f"  {eng['_key']}  {old_email}  ->  {email}  (team={team_key})")
        if apply:
            # normalise engineer email
            if email != old_email:
                eng_col.update({"_key": eng["_key"], "email": email})
            # upsert engineer login (replace if exists)
            users.import_bulk([{
                "email": email,
                "password_hash": pw_hash,
                "role": "engineer",
                "first_name": first,
                "last_name": last,
                "engineer_key": eng["_key"],
                "team_key": team_key,
                "is_active": True,
            }], on_duplicate="replace")
        created += 1

    # normalise team escalation contacts to the new domain
    teams = db.collection("teams")
    lead_changes = 0
    for t in teams.all():
        ec = t.get("escalation_contact")
        if ec and ec.endswith(OLD_DOMAIN):
            new_ec = to_new_domain(ec)
            print(f"  team {t['_key']}: {ec} -> {new_ec}")
            if apply:
                teams.update({"_key": t["_key"], "escalation_contact": new_ec})
            lead_changes += 1

    verb = "created/updated" if apply else "would be created/updated (dry run — use --apply)"
    print(f"\n{created} engineer login(s) {verb}; {lead_changes} team escalation contact(s) updated.")
    if apply:
        print(f"All engineer logins use password: {ENG_PASSWORD}")


if __name__ == "__main__":
    main()
