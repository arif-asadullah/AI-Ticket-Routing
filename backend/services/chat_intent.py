"""Rule-based intent parser for grounded chat. No LLM needed."""

import re

# Known categories and team names for matching
CATEGORIES = [
    "infrastructure", "application", "database",
    "network", "security", "access management",
]

TEAM_NAMES = [
    "infrastructure ops", "application support", "database admin",
    "network operations", "security operations", "access management",
]

# Status keywords
STATUSES = ["routed", "escalated", "in_progress", "in progress", "resolved", "closed", "open"]


def parse_intent(message: str) -> dict:
    """Parse user message into intent + entities.

    Returns: { intent: str, entities: dict }
    Intents: ticket_lookup, ticket_list, team_info, stats,
             engineer_info, category_info, resolution_info, general_it
    """
    text = message.lower().strip()

    # Fix common typos
    words = text.split()
    text = " ".join(_TYPO_MAP.get(w, w) for w in words)

    # ── Ticket lookup by ID ──
    # Matches: "ticket #5", "ticket 5", "T-5", "#5", "ticket id 5"
    ticket_id_match = re.search(
        r'(?:ticket\s*(?:#|id\s*)?|#|T-)(\d+)', message, re.IGNORECASE
    )
    if ticket_id_match:
        tid = ticket_id_match.group(1)

        # Check if asking about resolution
        if _has_any(text, ["resolution", "resolved", "fix", "how was it fixed", "solution"]):
            return {"intent": "resolution_info", "entities": {"ticket_id": tid}}

        # Check if asking about who is working on it
        if _has_any(text, ["who is working", "assigned to", "picked up", "who handles", "engineer"]):
            return {"intent": "engineer_info", "entities": {"ticket_id": tid}}

        # Default: full ticket lookup
        return {"intent": "ticket_lookup", "entities": {"ticket_id": tid}}

    # ── Server info (graph: ownership, dependencies, hosted services) ──
    # Matches seeded server keys like prod-db-01, prod-k8s-master, staging-db-01.
    server_match = re.search(r'\b((?:prod|staging)-[a-z0-9]+(?:-[a-z0-9]+)*)\b', text)
    if server_match:
        server_directed = _has_any(text, [
            "own", "manage", "responsible", "depend", "dependenc",
            "host", "runs on", "run on", "services on", "service on",
            "what's on", "whats on", "about",
        ])
        # Trigger unless it's clearly a ticket-list query that happens to name a server
        if server_directed or not _has_any(text, ["ticket", "tickets"]):
            return {"intent": "server_info", "entities": {"server": server_match.group(1)}}

    # ── Stats queries ──
    if _has_any(text, [
        "how many tickets", "total tickets", "ticket count",
        "average confidence", "avg confidence",
        "escalation rate", "escalated rate",
        "resolution time", "avg resolution",
        "classifier agreement", "agreement rate",
        "statistics", "stats", "metrics", "dashboard numbers",
        "helpfulness", "feedback rate",
    ]):
        return {"intent": "stats", "entities": {}}

    # ── Team info ──
    matched_team = _match_team(text)
    if matched_team or _has_any(text, [
        "which team", "what team", "who is the team", "team handling",
        "team members", "team info", "team responsible", "team manages",
        "handled by which", "who handles", "expertise", "areas of expertise",
    ]):
        entities = {}
        if matched_team:
            entities["team_name"] = matched_team
        # Check if a category is mentioned to find the team for that category
        matched_cat = _match_category(text)
        if matched_cat:
            entities["category"] = matched_cat
        return {"intent": "team_info", "entities": entities}

    # ── Ticket list queries ──
    matched_status = _match_status(text)
    matched_cat = _match_category(text)
    has_ticket_word = _has_any(text, ["ticket", "tickets", "issues", "issue"])
    if _has_any(text, [
        "my tickets", "all tickets", "list tickets", "show tickets",
        "open tickets", "pending tickets", "recent tickets",
    ]) or (matched_status and has_ticket_word) or (
        _has_any(text, ["all", "show", "list", "get"]) and has_ticket_word
    ):
        entities = {}
        if matched_status:
            entities["status"] = matched_status
        if matched_cat:
            entities["category"] = matched_cat
        # "my tickets" / "tickets I raised" → scope to the asking user
        if re.search(r"\b(?:my|mine)\b|i (?:submitted|raised|created|opened)", text):
            entities["mine"] = True
        return {"intent": "ticket_list", "entities": entities}

    # ── Category info (category + ticket words) ──
    if matched_cat and has_ticket_word:
        return {"intent": "category_info", "entities": {"category": matched_cat}}

    # ── Engineer / assignment queries (without ticket ID) ──
    if _has_any(text, ["who is working", "who handles", "assigned", "picked up"]):
        entities = {}
        if matched_cat:
            entities["category"] = matched_cat
        return {"intent": "engineer_info", "entities": entities}

    # ── Resolution queries (without ticket ID) ──
    if _has_any(text, ["how to fix", "resolution for", "fix for", "solution for"]):
        entities = {}
        if matched_cat:
            entities["category"] = matched_cat
        return {"intent": "resolution_info", "entities": entities}

    # ── No intent matched → general IT ──
    return {"intent": "general_it", "entities": {}}


def _has_any(text: str, keywords: list[str]) -> bool:
    """Check if text contains any of the keywords."""
    return any(kw in text for kw in keywords)


# Common typos/misspellings → normalized
_TYPO_MAP = {
    "tickts": "tickets", "tckets": "tickets", "tikets": "tickets", "ticktes": "tickets",
    "tciket": "ticket", "tikcet": "ticket", "tkt": "ticket",
    "datadbse": "database", "databse": "database", "datbase": "database",
    "infrastrcture": "infrastructure", "infrastrucutre": "infrastructure", "infra": "infrastructure",
    "applcation": "application", "applicaton": "application",
    "netwrk": "network", "nework": "network",
    "secuirty": "security", "securty": "security",
    "acess": "access", "managment": "management", "managemnt": "management",
    "esculated": "escalated", "esclated": "escalated",
    "resoled": "resolved", "resovled": "resolved",
    "staus": "status", "stauts": "status",
    "enginner": "engineer", "engineeer": "engineer",
}


def _match_category(text: str) -> str | None:
    """Find a category name in the text. Returns proper-case name."""
    for cat in CATEGORIES:
        if cat in text:
            return cat.title() if cat != "access management" else "Access Management"
    # Short aliases
    aliases = {
        "infra": "Infrastructure",
        "app": "Application",
        "db": "Database",
        "net": "Network",
        "sec": "Security",
        "iam": "Access Management",
        "access": "Access Management",
        "ldap": "Access Management",
    }
    for alias, cat in aliases.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', text):
            return cat
    return None


def _match_team(text: str) -> str | None:
    """Find a team name in the text. Returns proper-case name."""
    team_map = {
        "infrastructure ops": "Infrastructure Ops",
        "application support": "Application Support",
        "database admin": "Database Admin",
        "network operations": "Network Operations",
        "security operations": "Security Operations",
        "access management": "Access Management",
    }
    for key, name in team_map.items():
        if key in text:
            return name
    return None


def _match_status(text: str) -> str | None:
    """Find a ticket status in the text."""
    status_map = {
        "routed": "routed",
        "escalated": "escalated",
        "in progress": "in_progress",
        "in_progress": "in_progress",
        "resolved": "resolved",
        "closed": "closed",
        "open": "routed",
        "pending": "escalated",
    }
    for key, status in status_map.items():
        if key in text:
            return status
    return None
