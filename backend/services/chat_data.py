"""Data fetcher and grounded prompt builder for zero-hallucination chat."""

import logging

logger = logging.getLogger(__name__)


async def fetch_chat_data(intent: dict, db, user: dict) -> dict:
    """Query ArangoDB based on parsed intent.

    Returns: { found: bool, data: dict|list, summary: str }
    - found=False + summary → return summary directly, skip LLM
    - found=True + data → feed data into grounded LLM prompt
    """
    intent_type = intent["intent"]
    entities = intent.get("entities", {})

    try:
        if intent_type == "ticket_lookup":
            return _fetch_ticket(db, entities.get("ticket_id"), user)

        if intent_type == "ticket_list":
            return _fetch_ticket_list(db, entities, user)

        if intent_type == "team_info":
            return _fetch_team_info(db, entities)

        if intent_type == "stats":
            return _fetch_stats(db, user)

        if intent_type == "engineer_info":
            return _fetch_engineer_info(db, entities, user)

        if intent_type == "category_info":
            return _fetch_category_info(db, entities, user)

        if intent_type == "resolution_info":
            return _fetch_resolution_info(db, entities, user)

        if intent_type == "server_info":
            return _fetch_server_info(db, entities)

    except Exception as exc:
        logger.error("Chat data fetch failed for %s: %s", intent_type, exc)
        return {"found": False, "data": {}, "summary": "Sorry, I encountered an error looking that up. Please try again."}

    return {"found": False, "data": {}, "summary": "I couldn't understand what you're looking for."}


def _fetch_ticket(db, ticket_id: str | None, user: dict) -> dict:
    """Fetch a single ticket by ID."""
    if not ticket_id:
        return {"found": False, "data": {}, "summary": "Please provide a ticket ID (e.g., 'ticket #5')."}

    doc = db.collection("tickets").get(ticket_id)
    if not doc:
        return {"found": False, "data": {}, "summary": f"No ticket found with ID #{ticket_id}."}

    if doc.get("_source") != "user":
        return {"found": False, "data": {}, "summary": f"No ticket found with ID #{ticket_id}."}

    # Team scoping
    if not _can_access_ticket(doc, user, db):
        return {"found": False, "data": {}, "summary": f"You don't have access to ticket #{ticket_id}."}

    # Fetch audit trail
    audit = []
    try:
        cursor = db.aql.execute(
            "FOR a IN audit_log FILTER a.ticket_id == @tid SORT a.created_at ASC RETURN a",
            bind_vars={"tid": ticket_id},
        )
        audit = list(cursor)
    except Exception:
        pass

    ticket_data = _format_ticket(doc)
    ticket_data["audit_trail"] = [
        {"action": a.get("action"), "actor": a.get("actor"), "time": a.get("created_at"), "details": a.get("reasoning")}
        for a in audit
    ]

    return {"found": True, "data": ticket_data, "summary": ""}


def _fetch_ticket_list(db, entities: dict, user: dict) -> dict:
    """Fetch a list of tickets with optional filters."""
    filters = ["t._source == 'user'"]
    if entities.get("status"):
        filters.append(f"t.status == '{entities['status']}'")
    if entities.get("category"):
        filters.append(f"t.category == '{entities['category']}'")

    # Team scoping
    if user["role"] == "engineer":
        team_name = _resolve_team_name(db, user)
        if team_name:
            filters.append(f"t.routed_to == '{team_name}'")
    elif user["role"] == "user":
        filters.append(f"t.submitted_by == '{user['email']}'")

    filter_str = " AND ".join(filters)
    query = f"FOR t IN tickets FILTER {filter_str} SORT t.created_at DESC LIMIT 10 RETURN t"

    try:
        cursor = db.aql.execute(query)
        tickets = [_format_ticket(t) for t in cursor]
    except Exception as exc:
        logger.error("Ticket list query failed: %s", exc)
        return {"found": False, "data": {}, "summary": "Failed to fetch tickets."}

    if not tickets:
        desc = []
        if entities.get("status"):
            desc.append(f"status '{entities['status']}'")
        if entities.get("category"):
            desc.append(f"category '{entities['category']}'")
        filter_desc = " with " + " and ".join(desc) if desc else ""
        return {"found": False, "data": {}, "summary": f"No tickets found{filter_desc}."}

    return {"found": True, "data": {"tickets": tickets, "count": len(tickets)}, "summary": ""}


def _fetch_team_info(db, entities: dict) -> dict:
    """Fetch team details and members."""
    team_name = entities.get("team_name")
    category = entities.get("category")

    # If category given but no team, look up the team for that category
    if category and not team_name:
        try:
            cursor = db.aql.execute(
                "FOR r IN routing_rules FILTER r.category == @cat AND r.is_active == true "
                "LIMIT 1 FOR t IN teams FILTER t._key == r.team_key RETURN t",
                bind_vars={"cat": category},
            )
            team_doc = next(cursor, None)
            if team_doc:
                team_name = team_doc.get("name")
        except Exception:
            pass

    if not team_name:
        # Return all teams
        try:
            cursor = db.aql.execute("FOR t IN teams RETURN t")
            teams = []
            for t in cursor:
                members = _get_team_members(db, t["_key"])
                teams.append({
                    "name": t.get("name"),
                    "domain": t.get("domain"),
                    "members": members,
                })
            if not teams:
                return {"found": False, "data": {}, "summary": "No teams found in the system."}
            return {"found": True, "data": {"teams": teams}, "summary": ""}
        except Exception:
            return {"found": False, "data": {}, "summary": "Failed to fetch team information."}

    # Specific team lookup
    try:
        cursor = db.aql.execute(
            "FOR t IN teams FILTER t.name == @name LIMIT 1 RETURN t",
            bind_vars={"name": team_name},
        )
        team_doc = next(cursor, None)
    except Exception:
        team_doc = None

    if not team_doc:
        return {"found": False, "data": {}, "summary": f"No team found with name '{team_name}'."}

    members = _get_team_members(db, team_doc["_key"])
    team_data = {
        "name": team_doc.get("name"),
        "domain": team_doc.get("domain"),
        "members": members,
    }
    return {"found": True, "data": team_data, "summary": ""}


def _fetch_stats(db, user: dict) -> dict:
    """Fetch aggregated ticket statistics."""
    team_filter = ""
    bind_vars = {}
    if user["role"] == "engineer":
        team_name = _resolve_team_name(db, user)
        if team_name:
            team_filter = "FILTER t.routed_to == @team_name"
            bind_vars["team_name"] = team_name

    query = f"""
    LET user_tickets = (
        FOR t IN tickets FILTER t._source == "user" {team_filter} RETURN t
    )
    LET total = LENGTH(user_tickets)
    LET by_status = (
        FOR t IN user_tickets COLLECT st = t.status WITH COUNT INTO cnt RETURN {{status: st, count: cnt}}
    )
    LET by_category = (
        FOR t IN user_tickets COLLECT cat = t.category WITH COUNT INTO cnt SORT cnt DESC RETURN {{category: cat, count: cnt}}
    )
    LET avg_conf = AVERAGE(FOR t IN user_tickets FILTER t.confidence_score != null RETURN t.confidence_score)
    LET escalated = LENGTH(FOR t IN user_tickets FILTER t.status == "escalated" RETURN 1)
    RETURN {{
        total: total,
        by_status: by_status,
        by_category: by_category,
        avg_confidence: ROUND((avg_conf OR 0) * 1000) / 1000,
        escalation_rate: total > 0 ? ROUND(escalated * 1000 / total) / 1000 : 0
    }}
    """
    try:
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        result = next(cursor, {})
    except Exception as exc:
        logger.error("Stats query failed: %s", exc)
        return {"found": False, "data": {}, "summary": "Failed to fetch statistics."}

    if not result or result.get("total", 0) == 0:
        return {"found": False, "data": {}, "summary": "No ticket data available yet."}

    return {"found": True, "data": result, "summary": ""}


def _fetch_engineer_info(db, entities: dict, user: dict) -> dict:
    """Fetch who is working on a ticket or handles a category."""
    ticket_id = entities.get("ticket_id")
    if ticket_id:
        doc = db.collection("tickets").get(ticket_id)
        if not doc or doc.get("_source") != "user":
            return {"found": False, "data": {}, "summary": f"No ticket found with ID #{ticket_id}."}
        if not _can_access_ticket(doc, user, db):
            return {"found": False, "data": {}, "summary": f"You don't have access to ticket #{ticket_id}."}

        data = {
            "ticket_id": ticket_id,
            "title": doc.get("title"),
            "status": doc.get("status"),
            "routed_to": doc.get("routed_to"),
            "picked_up_by": doc.get("picked_up_by"),
        }
        if not data["picked_up_by"]:
            data["note"] = "This ticket has not been picked up by any engineer yet."
        return {"found": True, "data": data, "summary": ""}

    # Category-based: who handles this category
    category = entities.get("category")
    if category:
        try:
            cursor = db.aql.execute(
                "FOR r IN routing_rules FILTER r.category == @cat AND r.is_active == true "
                "LIMIT 1 FOR t IN teams FILTER t._key == r.team_key RETURN t",
                bind_vars={"cat": category},
            )
            team_doc = next(cursor, None)
            if team_doc:
                members = _get_team_members(db, team_doc["_key"])
                return {"found": True, "data": {
                    "category": category,
                    "team": team_doc.get("name"),
                    "members": members,
                }, "summary": ""}
        except Exception:
            pass
        return {"found": False, "data": {}, "summary": f"No team assignment found for category '{category}'."}

    return {"found": False, "data": {}, "summary": "Please specify a ticket ID or category."}


def _fetch_category_info(db, entities: dict, user: dict) -> dict:
    """Fetch ticket info for a specific category."""
    category = entities.get("category")
    if not category:
        return {"found": False, "data": {}, "summary": "Please specify a category."}

    filters = [f"t._source == 'user'", f"t.category == '{category}'"]
    if user["role"] == "engineer":
        team_name = _resolve_team_name(db, user)
        if team_name:
            filters.append(f"t.routed_to == '{team_name}'")
    elif user["role"] == "user":
        filters.append(f"t.submitted_by == '{user['email']}'")

    filter_str = " AND ".join(filters)
    try:
        cursor = db.aql.execute(
            f"FOR t IN tickets FILTER {filter_str} SORT t.created_at DESC LIMIT 10 RETURN t"
        )
        tickets = [_format_ticket(t) for t in cursor]

        count_cursor = db.aql.execute(
            f"FOR t IN tickets FILTER {filter_str} COLLECT WITH COUNT INTO cnt RETURN cnt"
        )
        total = next(count_cursor, 0)
    except Exception as exc:
        logger.error("Category query failed: %s", exc)
        return {"found": False, "data": {}, "summary": f"Failed to fetch {category} tickets."}

    if total == 0:
        return {"found": False, "data": {}, "summary": f"No tickets found in the '{category}' category."}

    return {"found": True, "data": {
        "category": category,
        "total": total,
        "recent_tickets": tickets,
    }, "summary": ""}


def _fetch_resolution_info(db, entities: dict, user: dict) -> dict:
    """Fetch resolution details for a ticket."""
    ticket_id = entities.get("ticket_id")
    if not ticket_id:
        return {"found": False, "data": {}, "summary": "Please specify a ticket ID to look up its resolution (e.g., 'how was ticket #5 resolved?')."}

    doc = db.collection("tickets").get(ticket_id)
    if not doc or doc.get("_source") != "user":
        return {"found": False, "data": {}, "summary": f"No ticket found with ID #{ticket_id}."}
    if not _can_access_ticket(doc, user, db):
        return {"found": False, "data": {}, "summary": f"You don't have access to ticket #{ticket_id}."}

    if doc.get("status") not in ("resolved", "closed"):
        return {"found": True, "data": {
            "ticket_id": ticket_id,
            "title": doc.get("title"),
            "status": doc.get("status"),
            "note": "This ticket has not been resolved yet.",
        }, "summary": ""}

    # Get resolution via edge traversal
    resolution = None
    try:
        cursor = db.aql.execute(
            "FOR res IN 1..1 OUTBOUND CONCAT('tickets/', @tid) resolved_with LIMIT 1 RETURN res",
            bind_vars={"tid": ticket_id},
        )
        resolution = next(cursor, None)
    except Exception:
        pass

    data = {
        "ticket_id": ticket_id,
        "title": doc.get("title"),
        "status": doc.get("status"),
        "resolved_at": doc.get("resolved_at"),
        "resolution_steps": resolution.get("steps") if resolution else None,
        "effectiveness": resolution.get("effectiveness") if resolution else None,
        "suggested_resolution": doc.get("suggested_resolution"),
        "suggested_runbook": doc.get("suggested_runbook"),
    }
    return {"found": True, "data": data, "summary": ""}


# ── Helpers ──

def _format_ticket(doc: dict) -> dict:
    """Extract relevant fields from a ticket document."""
    return {
        "id": doc.get("_key"),
        "title": doc.get("title"),
        "description": doc.get("description", "")[:200],
        "category": doc.get("category"),
        "priority": doc.get("priority"),
        "status": doc.get("status"),
        "confidence": doc.get("confidence_score"),
        "routed_to": doc.get("routed_to"),
        "picked_up_by": doc.get("picked_up_by"),
        "submitted_by": doc.get("submitted_by"),
        "recommended_expert": doc.get("recommended_expert"),
        "created_at": doc.get("created_at"),
        "resolved_at": doc.get("resolved_at"),
    }


def _can_access_ticket(doc: dict, user: dict, db) -> bool:
    """Check if user can access this ticket (team scoping)."""
    if user["role"] == "admin":
        return True
    if user["role"] == "user":
        return doc.get("submitted_by") == user["email"]
    # Engineer: must be on the ticket's team
    team_name = _resolve_team_name(db, user)
    return doc.get("routed_to") == team_name


def _resolve_team_name(db, user: dict) -> str | None:
    """Resolve team_key to team name."""
    team_key = user.get("team_key")
    if not team_key:
        return None
    try:
        team_doc = db.collection("teams").get(team_key)
        return team_doc.get("name") if team_doc else None
    except Exception:
        return None


def _get_team_members(db, team_key: str) -> list[dict]:
    """Get team members via member_of edge traversal."""
    try:
        cursor = db.aql.execute(
            "FOR eng IN 1..1 INBOUND CONCAT('teams/', @key) member_of RETURN eng",
            bind_vars={"key": team_key},
        )
        return [
            {"name": e.get("name"), "expertise": e.get("expertise", []), "email": e.get("email")}
            for e in cursor
        ]
    except Exception:
        return []


def _fetch_server_info(db, entities: dict) -> dict:
    """Fetch a server's owner team, hosted services and dependent services from the graph."""
    server_key = entities.get("server")
    if not server_key:
        return {"found": False, "data": {}, "summary": "Please specify a server (e.g., 'who owns prod-db-01')."}

    if not db.collection("servers").get(server_key):
        return {"found": False, "data": {}, "summary": f"I don't have a record of server {server_key}."}

    query = """
    LET srv = DOCUMENT(CONCAT("servers/", @key))
    LET team = FIRST(FOR t IN 1..1 OUTBOUND srv managed_by RETURN t)
    LET hosted = (FOR svc IN 1..1 OUTBOUND srv hosts RETURN svc.name)
    LET dependents = UNIQUE(
        FOR svc IN 1..1 OUTBOUND srv hosts
            FOR dep IN 1..1 INBOUND svc depends_on
                RETURN dep.name
    )
    LET experts = team == null ? [] : (
        FOR eng IN 1..1 INBOUND team member_of
            RETURN { name: eng.name, expertise: eng.expertise }
    )
    RETURN {
        server: srv._key,
        type: srv.type,
        datacenter: srv.datacenter,
        owner_team: team.name,
        team_domain: team.domain,
        hosted_services: hosted,
        dependent_services: dependents,
        experts: experts
    }
    """
    data = next(db.aql.execute(query, bind_vars={"key": server_key}), None)
    if not data:
        return {"found": False, "data": {}, "summary": f"I don't have graph details for server {server_key}."}

    return {"found": True, "data": data, "summary": ""}


def build_grounded_prompt(intent: dict, data: dict) -> str:
    """Build a system prompt with ONLY the fetched data.
    The LLM is instructed to answer ONLY from this context.
    """
    context = _format_data_as_text(intent["intent"], data)

    return f"""You are Mindy, DeskMind's AI assistant. You answer questions about IT tickets ONLY using the data provided below.

STRICT RULES:
- ONLY use the data provided in the CONTEXT section
- NEVER make up or guess ticket IDs, team names, statuses, engineer names, or any information
- If the CONTEXT doesn't contain the answer, say "I don't have that information in my records"
- Always cite ticket IDs (e.g., #5) and team names exactly as shown in the data
- Be concise and direct — present the data clearly
- Format numbers, dates, and statuses in a readable way

CONTEXT:
{context}"""


def _format_data_as_text(intent_type: str, data: dict) -> str:
    """Convert structured data to readable text for the LLM context."""
    lines = []

    if intent_type == "ticket_lookup":
        lines.append(f"Ticket #{data.get('id')}:")
        lines.append(f"  Title: {data.get('title')}")
        lines.append(f"  Description: {data.get('description')}")
        lines.append(f"  Category: {data.get('category')}")
        lines.append(f"  Priority: {data.get('priority')}")
        lines.append(f"  Status: {data.get('status')}")
        lines.append(f"  Confidence: {round((data.get('confidence') or 0) * 100)}%")
        lines.append(f"  Routed to: {data.get('routed_to') or 'Not assigned'}")
        lines.append(f"  Picked up by: {data.get('picked_up_by') or 'Not picked up yet'}")
        lines.append(f"  Submitted by: {data.get('submitted_by')}")
        lines.append(f"  Recommended expert: {data.get('recommended_expert') or 'None'}")
        lines.append(f"  Created: {data.get('created_at')}")
        lines.append(f"  Resolved: {data.get('resolved_at') or 'Not resolved'}")
        if data.get("audit_trail"):
            lines.append("  Audit Trail:")
            for a in data["audit_trail"]:
                lines.append(f"    - [{a.get('time')}] {a.get('action')} by {a.get('actor')}: {a.get('details', '')}")

    elif intent_type == "ticket_list":
        lines.append(f"Found {data.get('count', 0)} ticket(s):")
        for t in data.get("tickets", []):
            lines.append(f"  #{t['id']} | {t['title']} | {t['status']} | {t['priority']} | {t['category']} | routed to: {t.get('routed_to', 'N/A')}")

    elif intent_type == "team_info":
        if "teams" in data:
            for team in data["teams"]:
                lines.append(f"Team: {team['name']} (Domain: {team.get('domain', 'N/A')})")
                for m in team.get("members", []):
                    lines.append(f"  - {m['name']} | Expertise: {', '.join(m.get('expertise', []))}")
        else:
            lines.append(f"Team: {data.get('name')} (Domain: {data.get('domain', 'N/A')})")
            for m in data.get("members", []):
                lines.append(f"  - {m['name']} | Expertise: {', '.join(m.get('expertise', []))}")

    elif intent_type == "stats":
        lines.append(f"Total tickets: {data.get('total', 0)}")
        lines.append(f"Average confidence: {round((data.get('avg_confidence') or 0) * 100)}%")
        lines.append(f"Escalation rate: {round((data.get('escalation_rate') or 0) * 100)}%")
        if data.get("by_status"):
            lines.append("By status:")
            for s in data["by_status"]:
                lines.append(f"  {s['status']}: {s['count']}")
        if data.get("by_category"):
            lines.append("By category:")
            for c in data["by_category"]:
                lines.append(f"  {c['category']}: {c['count']}")

    elif intent_type == "engineer_info":
        if data.get("ticket_id"):
            lines.append(f"Ticket #{data['ticket_id']}: {data.get('title')}")
            lines.append(f"  Status: {data.get('status')}")
            lines.append(f"  Routed to team: {data.get('routed_to') or 'Not assigned'}")
            lines.append(f"  Picked up by: {data.get('picked_up_by') or 'Not picked up yet'}")
            if data.get("note"):
                lines.append(f"  Note: {data['note']}")
        elif data.get("team"):
            lines.append(f"Category '{data['category']}' is handled by team: {data['team']}")
            for m in data.get("members", []):
                lines.append(f"  - {m['name']} | Expertise: {', '.join(m.get('expertise', []))}")

    elif intent_type == "category_info":
        lines.append(f"Category: {data.get('category')}")
        lines.append(f"Total tickets: {data.get('total', 0)}")
        if data.get("recent_tickets"):
            lines.append("Recent tickets:")
            for t in data["recent_tickets"]:
                lines.append(f"  #{t['id']} | {t['title']} | {t['status']} | {t['priority']}")

    elif intent_type == "resolution_info":
        lines.append(f"Ticket #{data.get('ticket_id')}: {data.get('title')}")
        lines.append(f"  Status: {data.get('status')}")
        if data.get("note"):
            lines.append(f"  Note: {data['note']}")
        else:
            lines.append(f"  Resolved at: {data.get('resolved_at')}")
            if data.get("resolution_steps"):
                lines.append("  Resolution steps:")
                for i, step in enumerate(data["resolution_steps"], 1):
                    lines.append(f"    {i}. {step}")
            if data.get("effectiveness") is not None:
                lines.append(f"  Effectiveness: {round(data['effectiveness'] * 100)}%")
            if data.get("suggested_runbook"):
                lines.append(f"  Runbook: {data['suggested_runbook']}")

    elif intent_type == "server_info":
        lines.append(f"Server: {data.get('server')}")
        lines.append(f"  Type: {data.get('type')}")
        lines.append(f"  Datacenter: {data.get('datacenter')}")
        lines.append(f"  Owned/managed by team: {data.get('owner_team') or 'Unknown'}")
        if data.get("experts"):
            lines.append(f"  Team experts: {', '.join(e['name'] for e in data['experts'])}")
        lines.append(f"  Hosted services: {', '.join(data.get('hosted_services') or []) or 'None'}")
        lines.append(f"  Dependent services (rely on this server): {', '.join(data.get('dependent_services') or []) or 'None'}")

    return "\n".join(lines) if lines else "No data available."


def extract_entities(intent: dict, data: dict) -> list[dict]:
    """Extract entity metadata from fetched data for frontend chips.

    Returns list of: { type: "ticket"|"engineer"|"team"|"status"|"category",
                       value: str (display text), data: dict (tooltip info) }
    """
    entities = []
    intent_type = intent["intent"]
    seen = set()

    def _add(etype, value, edata):
        key = f"{etype}:{value}"
        if key not in seen and value:
            seen.add(key)
            entities.append({"type": etype, "value": str(value), "data": edata})

    if intent_type == "ticket_lookup":
        _add("ticket", f"#{data.get('id')}", {
            "id": data.get("id"), "title": data.get("title"),
            "status": data.get("status"), "category": data.get("category"),
            "priority": data.get("priority"), "routed_to": data.get("routed_to"),
            "confidence": data.get("confidence"), "created_at": data.get("created_at"),
        })
        if data.get("routed_to"):
            _add("team", data["routed_to"], {"name": data["routed_to"]})
        if data.get("recommended_expert"):
            _add("engineer", data["recommended_expert"], {"name": data["recommended_expert"]})
        if data.get("picked_up_by"):
            _add("engineer", data["picked_up_by"], {"name": data["picked_up_by"], "note": "Currently working on this ticket"})
        if data.get("status"):
            _add("status", data["status"], {})
        if data.get("category"):
            _add("category", data["category"], {})

    elif intent_type == "ticket_list":
        for t in data.get("tickets", []):
            _add("ticket", f"#{t['id']}", {
                "id": t["id"], "title": t.get("title"),
                "status": t.get("status"), "category": t.get("category"),
                "priority": t.get("priority"), "routed_to": t.get("routed_to"),
            })

    elif intent_type == "team_info":
        if "teams" in data:
            for team in data["teams"]:
                _add("team", team["name"], {
                    "name": team["name"], "domain": team.get("domain"),
                    "members": team.get("members", []),
                })
                for m in team.get("members", []):
                    _add("engineer", m["name"], m)
        else:
            _add("team", data.get("name"), {
                "name": data.get("name"), "domain": data.get("domain"),
                "members": data.get("members", []),
            })
            for m in data.get("members", []):
                _add("engineer", m["name"], m)

    elif intent_type == "engineer_info":
        if data.get("ticket_id"):
            _add("ticket", f"#{data['ticket_id']}", {
                "id": data["ticket_id"], "title": data.get("title"),
                "status": data.get("status"), "routed_to": data.get("routed_to"),
            })
            if data.get("routed_to"):
                _add("team", data["routed_to"], {"name": data["routed_to"]})
            if data.get("picked_up_by"):
                _add("engineer", data["picked_up_by"], {"name": data["picked_up_by"]})
        elif data.get("team"):
            _add("team", data["team"], {"name": data["team"]})
            for m in data.get("members", []):
                _add("engineer", m["name"], m)

    elif intent_type == "category_info":
        _add("category", data.get("category"), {})
        for t in data.get("recent_tickets", []):
            _add("ticket", f"#{t['id']}", {
                "id": t["id"], "title": t.get("title"),
                "status": t.get("status"), "priority": t.get("priority"),
            })

    elif intent_type == "resolution_info":
        _add("ticket", f"#{data.get('ticket_id')}", {
            "id": data.get("ticket_id"), "title": data.get("title"),
            "status": data.get("status"),
        })

    elif intent_type == "server_info":
        _add("server", data.get("server"), {
            "type": data.get("type"), "datacenter": data.get("datacenter"),
            "owner_team": data.get("owner_team"),
        })
        if data.get("owner_team"):
            _add("team", data["owner_team"], {"name": data["owner_team"], "domain": data.get("team_domain")})
        for e in data.get("experts", []):
            _add("engineer", e["name"], e)
        for svc in data.get("hosted_services", []):
            _add("service", svc, {"hosted_on": data.get("server")})
        for svc in data.get("dependent_services", []):
            _add("service", svc, {"depends_on_server": data.get("server")})

    return entities
