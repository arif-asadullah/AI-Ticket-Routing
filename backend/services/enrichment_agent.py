"""Autonomous Ticket Enrichment Agent.

When a user submits a vague ticket (LOW quality), this agent generates
personalized follow-up questions using:
- User's ticket history (common categories, servers)
- Knowledge graph context (servers, services, error codes)
- Similar past tickets (for reference)

The enrichment data includes clickable suggestions so the user can
answer with a single click, dramatically improving classification accuracy.
"""

import logging

logger = logging.getLogger(__name__)


def generate_enrichment(title: str, description: str, quality: str,
                        confidence: float, user_email: str | None,
                        entities: dict, embedding: list[float] | None,
                        db=None) -> dict | None:
    """Generate enrichment questions for vague tickets.

    Returns None if the ticket doesn't need enrichment (quality is HIGH
    and confidence is good). Otherwise returns a structured enrichment
    object with personalized questions and suggestions.
    """
    # Only enrich LOW quality or low confidence tickets
    if quality == "HIGH" or (quality == "MEDIUM" and confidence >= 0.70):
        return None

    has_servers = bool(entities.get("servers"))
    has_services = bool(entities.get("services"))
    has_errors = bool(entities.get("error_codes"))
    desc_len = len(description.strip())

    # Determine reason
    reasons = []
    if desc_len < 50:
        reasons.append(f"Description is only {desc_len} characters")
    if not has_servers and not has_services:
        reasons.append("No server or service mentioned")
    if not has_errors:
        reasons.append("No error code detected")

    if not reasons:
        return None

    # Gather user context from history
    user_context = _get_user_context(user_email, db)

    # Build questions dynamically
    questions = []

    # Q1: Server — only if no server detected
    if not has_servers:
        server_suggestions = user_context.get("common_servers", [])[:4]
        if not server_suggestions and db:
            # Fallback: get top servers from recent tickets
            server_suggestions = _get_common_servers(db)
        questions.append({
            "id": "server",
            "question": "Which server or system is affected?",
            "type": "select",
            "suggestions": server_suggestions + (["Not sure"] if server_suggestions else []),
            "hint": f"You usually report issues about {server_suggestions[0]}" if server_suggestions else "Enter the hostname or system name",
        })

    # Q2: Error/symptom — only if no error detected
    if not has_errors:
        questions.append({
            "id": "error",
            "question": "What error message or symptom are you seeing?",
            "type": "text",
            "suggestions": ["Connection refused", "Timeout", "Out of memory", "Slow response", "Service unavailable", "Permission denied"],
            "hint": "Include the exact error message if possible",
        })

    # Q3: Impact — always ask for vague tickets
    questions.append({
        "id": "impact",
        "question": "What's the business impact?",
        "type": "select",
        "suggestions": ["Production down", "Performance degraded", "Dev/staging only", "No impact yet"],
        "hint": "This helps us prioritize accurately",
    })

    # Q4: Timeline — only if description is very short
    if desc_len < 30:
        questions.append({
            "id": "since",
            "question": "When did this start?",
            "type": "select",
            "suggestions": ["Just now", "Last hour", "Today", "Ongoing for days"],
            "hint": None,
        })

    # Find similar tickets for reference
    similar = _find_similar_tickets(embedding, db) if embedding and db else []

    return {
        "needed": True,
        "reason": ". ".join(reasons),
        "user_context": user_context,
        "questions": questions,
        "similar_tickets": similar,
    }


def _get_user_context(user_email: str | None, db) -> dict:
    """Pull user's ticket history for personalization."""
    context = {
        "common_categories": [],
        "common_servers": [],
        "ticket_count": 0,
    }
    if not user_email or not db:
        return context

    try:
        cursor = db.aql.execute(
            """FOR t IN tickets
                FILTER t.submitted_by == @email AND t._source == "user"
                SORT t.created_at DESC
                LIMIT 10
                RETURN {
                    category: t.category,
                    title: t.title,
                    description: LEFT(t.description, 100)
                }""",
            bind_vars={"email": user_email},
        )
        history = list(cursor)
        context["ticket_count"] = len(history)

        # Common categories
        cat_counts = {}
        for t in history:
            cat = t.get("category")
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        context["common_categories"] = sorted(cat_counts, key=cat_counts.get, reverse=True)[:3]

        # Extract server names from past ticket descriptions
        from backend.services.entity_extractor import entity_extractor
        servers_seen = {}
        for t in history:
            text = f"{t.get('title', '')} {t.get('description', '')}"
            ents = entity_extractor.extract(text, db=db)
            for s in ents.get("servers", []):
                servers_seen[s] = servers_seen.get(s, 0) + 1
        context["common_servers"] = sorted(servers_seen, key=servers_seen.get, reverse=True)[:4]

    except Exception as exc:
        logger.warning("Failed to get user context: %s", exc)

    return context


def _get_common_servers(db) -> list[str]:
    """Get commonly mentioned servers from recent tickets."""
    try:
        cursor = db.aql.execute(
            """FOR s IN servers
                SORT s._key ASC
                LIMIT 6
                RETURN s._key"""
        )
        return list(cursor)
    except Exception:
        return []


def _find_similar_tickets(embedding: list[float], db, limit: int = 3) -> list[dict]:
    """Find similar past tickets for reference."""
    try:
        cursor = db.aql.execute(
            """FOR t IN tickets
                FILTER t.status IN ["closed", "resolved"] AND t.embedding != null
                LET sim = COSINE_SIMILARITY(t.embedding, @embedding)
                FILTER sim > 0.60
                SORT sim DESC
                LIMIT @limit
                RETURN {
                    id: t._key,
                    title: t.title,
                    category: t.category,
                    similarity: ROUND(sim * 100) / 100
                }""",
            bind_vars={"embedding": embedding, "limit": limit},
        )
        return list(cursor)
    except Exception as exc:
        logger.warning("Failed to find similar tickets: %s", exc)
        return []


def build_enriched_description(original_description: str, answers: dict) -> str:
    """Build a natural-sounding enriched description from the original + answers.

    Instead of key-value pairs, generates proper sentences that the LLM
    and embedding model can understand well.
    """
    parts = [original_description.strip()]

    sentences = []
    server = answers.get("server", "").strip()
    error = answers.get("error", "").strip()
    impact = answers.get("impact", "").strip()
    since = answers.get("since", "").strip()

    if server and server.lower() != "not sure":
        sentences.append(f"The affected server is {server}.")
    if error:
        sentences.append(f"The error observed is: {error}.")
    if impact:
        if impact.lower() == "production down":
            sentences.append("This is causing a production outage affecting end users.")
        elif impact.lower() == "performance degraded":
            sentences.append("This is causing performance degradation in production.")
        elif impact.lower() == "dev/staging only":
            sentences.append("This is only affecting the development/staging environment.")
        else:
            sentences.append(f"Business impact: {impact}.")
    if since:
        sentences.append(f"The issue started {since.lower()}.")

    # Add any other custom answers
    for key, value in answers.items():
        if key not in ("server", "error", "impact", "since") and value and value.strip():
            sentences.append(f"{key.replace('_', ' ').title()}: {value}.")

    if sentences:
        parts.append("\n\n" + " ".join(sentences))

    return "\n".join(parts)
