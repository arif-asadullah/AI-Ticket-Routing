"""
AI Resolution Generator — generates custom step-by-step fixes using the LLM.

Instead of only retrieving past resolutions, this service uses the LLM to
GENERATE a tailored resolution grounded in:
  1. Similar past resolutions (with effectiveness scores)
  2. Knowledge graph context (server, services, team, experts)
  3. Error code patterns (known fixes)
  4. The ticket's classified category + priority

Quality gate: only generates when we have reference context (no hallucination).
"""

import json
import logging

import httpx

from backend.core.config import settings
from backend.services.circuit_breaker import ollama_breaker

logger = logging.getLogger(__name__)

TIMEOUT = 120.0

SYSTEM_PROMPT = """You are DeskMind, an expert IT operations engineer. Your job is to generate a step-by-step resolution plan for IT support tickets.

RULES:
1. Base your resolution ONLY on the reference solutions and context provided. Do NOT invent server names, IP addresses, or commands that are not in the context.
2. Generate 3-7 clear, actionable steps. Each step should be one sentence.
3. Order steps from diagnosis to fix to verification.
4. If the context includes server names, service names, or specific commands from past resolutions — use them.
5. Include a verification step at the end (e.g., "Verify the service is responding normally").
6. Adapt past resolutions to the SPECIFIC ticket — don't just copy them blindly.

Return ONLY valid JSON:
{
  "steps": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
  "reasoning": "Brief explanation of why these steps should work",
  "confidence": "high" or "medium" or "low",
  "sources_used": ["brief description of which reference solutions informed this"]
}"""


def _build_resolution_context(
    title: str,
    description: str,
    category: str,
    priority: str,
    entities: dict,
    similar_tickets: list[dict],
    graph_context: dict | None,
    error_codes: list[dict],
) -> str:
    """Build a rich context prompt for the LLM."""
    sections = []

    # Ticket info
    sections.append(
        f"TICKET TO RESOLVE:\n"
        f"  Title: {title}\n"
        f"  Description: {description}\n"
        f"  Category: {category}\n"
        f"  Priority: {priority}"
    )

    # Entities
    if entities.get("servers"):
        sections.append(f"  Affected servers: {', '.join(entities['servers'])}")
    if entities.get("services"):
        sections.append(f"  Affected services: {', '.join(entities['services'])}")

    # Error codes
    if error_codes:
        err_lines = ["DETECTED ERROR PATTERNS:"]
        for err in error_codes[:5]:
            err_lines.append(f"  - {err.get('error_name', err.get('error_key', 'unknown'))}")
        sections.append("\n".join(err_lines))

    # Past resolutions (the grounding data)
    ref_resolutions = []
    for t in similar_tickets:
        if t.get("resolution_steps") and t.get("category") == category:
            ref_resolutions.append(t)
    # Also include close categories if we don't have enough
    if len(ref_resolutions) < 2:
        for t in similar_tickets:
            if t.get("resolution_steps") and t not in ref_resolutions:
                ref_resolutions.append(t)

    if ref_resolutions:
        lines = ["REFERENCE SOLUTIONS FROM SIMILAR PAST TICKETS:"]
        for i, t in enumerate(ref_resolutions[:5], 1):
            eff = t.get("effectiveness")
            eff_str = f" (effectiveness: {eff:.0%})" if eff else ""
            steps_text = " → ".join(t["resolution_steps"][:4])
            lines.append(
                f"  {i}. [{t['category']}] \"{t['title']}\"{eff_str}\n"
                f"     Steps: {steps_text}"
            )
        sections.append("\n".join(lines))

    # Graph context
    if graph_context and graph_context.get("managed_by_team"):
        infra_lines = [
            "INFRASTRUCTURE CONTEXT:",
            f"  Server type: {graph_context.get('server_type', 'unknown')}",
            f"  Datacenter: {graph_context.get('server_datacenter', 'unknown')}",
            f"  Managed by: {graph_context['managed_by_team']}",
        ]
        if graph_context.get("hosted_services"):
            infra_lines.append(f"  Services on server: {', '.join(graph_context['hosted_services'])}")
        if graph_context.get("dependent_services"):
            infra_lines.append(f"  Dependent services: {', '.join(graph_context['dependent_services'])}")
        if graph_context.get("experts"):
            experts = ", ".join(f"{e['name']} ({e.get('expertise', '')})" for e in graph_context["experts"][:3])
            infra_lines.append(f"  Team experts: {experts}")

        # Past tickets on same server
        past = graph_context.get("past_tickets_on_server", [])
        if past:
            infra_lines.append("  Recent issues on this server:")
            for pt in past[:3]:
                steps = " → ".join(pt["resolution_steps"][:2]) if pt.get("resolution_steps") else "no resolution"
                infra_lines.append(f"    - [{pt.get('category')}] {pt.get('title', '?')}: {steps}")

        sections.append("\n".join(infra_lines))

    return "\n\n".join(sections)


def _parse_response(text: str) -> dict | None:
    """Parse JSON from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "steps" in data:
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict) and "steps" in data:
                return data
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse resolution response: %s", text[:200])
    return None


async def generate_resolution(
    title: str,
    description: str,
    category: str,
    priority: str,
    entities: dict,
    similar_tickets: list[dict],
    graph_context: dict | None,
    error_codes: list[dict],
) -> dict | None:
    """
    Generate a custom resolution using the LLM, grounded in real data.

    Quality gate: only generates when we have at least 1 reference resolution.
    Returns None if no context available or LLM fails.

    Returns:
        {
            "steps": ["Step 1: ...", ...],
            "reasoning": "Why these steps should work",
            "confidence": "high" | "medium" | "low",
            "sources_used": ["description of references used"],
            "source": "ai_generated"
        }
    """
    # Quality gate: need at least 1 reference resolution
    has_reference = any(t.get("resolution_steps") for t in similar_tickets)
    has_graph = graph_context and graph_context.get("managed_by_team")
    has_errors = len(error_codes) > 0

    if not has_reference and not has_graph and not has_errors:
        logger.info("Resolution generator: no reference context, skipping")
        return None

    if not ollama_breaker.is_available:
        logger.warning("Resolution generator: circuit breaker open, skipping")
        return None

    context_text = _build_resolution_context(
        title, description, category, priority,
        entities, similar_tickets, graph_context, error_codes,
    )

    user_prompt = f"""{context_text}

Generate a step-by-step resolution plan for this {category} ticket ({priority} priority).
Base your steps on the reference solutions above. Adapt them to this specific situation.

Return ONLY valid JSON: {{"steps": [...], "reasoning": "...", "confidence": "high|medium|low", "sources_used": [...]}}"""

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": settings.LLM_RESOLUTION_MAX_TOKENS,
                    "keep_alive": settings.LLM_KEEP_ALIVE,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        result = _parse_response(content)
        if not result or not result.get("steps"):
            logger.warning("Resolution generator: empty or invalid response")
            return None

        # Validate steps
        steps = result["steps"]
        if not isinstance(steps, list) or len(steps) < 1:
            return None
        steps = [s for s in steps if isinstance(s, str) and len(s.strip()) > 5]
        if not steps:
            return None

        ollama_breaker.record_success()

        generated = {
            "steps": steps[:7],
            "reasoning": result.get("reasoning", ""),
            "confidence": result.get("confidence", "medium"),
            "sources_used": result.get("sources_used", []),
            "source": "ai_generated",
        }

        logger.info(
            "Resolution generated: %d steps, confidence=%s, sources=%d",
            len(generated["steps"]), generated["confidence"], len(generated["sources_used"]),
        )
        return generated

    except httpx.ConnectError:
        ollama_breaker.record_failure()
        logger.warning("Resolution generator: Ollama not reachable")
        return None
    except Exception as exc:
        ollama_breaker.record_failure()
        logger.error("Resolution generator failed: %s", exc)
        return None
