"""
LLM Classifier — Classifier 1 (weight: 0.40)

Sends ticket + all Stage 2 context to Qwen 2.5:3B via Ollama.
Uses root-cause analysis prompt with few-shot examples.
Accuracy: ~85% alone.
"""

import json
import logging

import httpx

from backend.core.config import settings
from backend.services.circuit_breaker import ollama_breaker
from backend.services.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

TIMEOUT = 120.0

SYSTEM_PROMPT = """You are DeskMind, an expert IT ticket classifier. Your job is to identify the ROOT CAUSE domain, not the symptom.

RULES:
1. Classify by ROOT CAUSE, not by symptom.

2. Categories (pick exactly ONE):
   - Infrastructure: Server hardware, OS, CPU/RAM/disk, VMs, Kubernetes NODES (not apps running on K8s), Docker daemon, server crashes, reboots
   - Application: App code bugs, API errors, HTTP 5xx from application logic, deployments, build failures, NGINX/Grafana/Prometheus CONFIG issues, frontend bugs
   - Database: PostgreSQL, MySQL, Redis, MongoDB, SQL queries, replication, connection pools, backups, data integrity
   - Network: DNS, VPN, firewall RULES, load balancers, SSL/TLS certificates, latency, packet loss, routing, BGP
   - Security: Malware, ransomware, breaches, vulnerabilities, CVEs, exploits, intrusions, phishing, unauthorized access attempts, security scanning
   - Access Management: LDAP, Active Directory, SSO, SAML, OAuth, MFA, RBAC, permissions, account lockouts, password issues, user provisioning, service account credentials, identity governance, group memberships

3. DISAMBIGUATION (critical — follow these strictly):
   - "locked out" / "can't login" / "login failed" → Access Management (NOT Security, unless explicitly a brute force attack or breach)
   - "firewall blocking traffic" → Network (NOT Security, unless explicitly a security policy violation)
   - "someone logged into my account" → Security (unauthorized access IS a security incident)
   - "nginx crashing" / "Grafana not loading" / "Prometheus errors" → Application (these are APPLICATION services, not Infrastructure)
   - "nginx load balancer timeout" → Network (load balancer is network infrastructure)
   - Only classify as Infrastructure if the SERVER HARDWARE or OS is the problem (CPU spike, RAM full, disk full, kernel panic, node down)
   - "accessibility" / "WCAG" → Application (web accessibility, NOT Access Management)
   - "SSL certificate expired" → Network (TLS is network layer)
   - "expired service account token" / "password expired" → Access Management (credential lifecycle)
   - "Redis cache issue" / "Redis OOM" → Database (Redis IS a database)
   - "Kubernetes pod not scheduling" / "node eviction" → Infrastructure (K8s resource management)
   - "Kubernetes deployment failing" / "pod crash loop" → Application (application on K8s)

4. EXAMPLES:
   Infrastructure: "prod-db-01 server unresponsive, cannot SSH, monitoring shows CPU at 100% for 2 hours"
   Application: "Grafana dashboards showing blank pages after v9.5 upgrade, all data sources connected but panels empty"
   Database: "PostgreSQL replication lag exceeding 30 seconds on prod-db-02, WAL replay falling behind"
   Network: "VPN users reporting intermittent disconnections, MTU mismatch suspected between tunnel endpoints"
   Security: "Detected unauthorized SSH login from unknown IP 45.33.xx.xx on prod-app-02 at 3am, not in our IP whitelist"
   Access Management: "50 users locked out of Active Directory after quarterly password rotation policy kicked in"

5. Priority:
   - critical: Production completely down, data loss risk, active security breach
   - high: Major feature broken, significant performance degradation
   - medium: Partial impact, workaround available
   - low: Minor issue, no immediate business impact

Return ONLY valid JSON: {"category": "...", "priority": "...", "confidence": 0.0-1.0, "reasoning": "..."}"""


def _build_context_section(context: RetrievalResult) -> str:
    """Build the context section of the prompt from Stage 2 results."""
    sections = []

    # Graph context
    graph = context.get("graph_context")
    if graph and graph.get("managed_by_team"):
        sections.append(
            f"INFRASTRUCTURE CONTEXT:\n"
            f"  Server type: {graph.get('server_type', 'unknown')}\n"
            f"  Datacenter: {graph.get('server_datacenter', 'unknown')}\n"
            f"  Managed by: {graph['managed_by_team']} (domain: {graph.get('managed_by_domain', '?')})\n"
            f"  Services on server: {', '.join(graph.get('hosted_services', []))}\n"
            f"  Dependent services: {', '.join(graph.get('dependent_services', []))}"
        )
        if graph.get("experts"):
            experts = ", ".join(f"{e['name']} ({e.get('role', '')})" for e in graph["experts"][:3])
            sections.append(f"  Experts: {experts}")

    # Similar tickets
    similar = context.get("similar_tickets", [])
    if similar:
        lines = ["SIMILAR PAST TICKETS:"]
        for i, t in enumerate(similar[:5], 1):
            res = f" → Resolution: {', '.join(t['resolution_steps'][:2])}" if t.get("resolution_steps") else ""
            lines.append(f"  {i}. [{t['category']}, {t.get('priority', '?')}] \"{t['title']}\"{res}")
        sections.append("\n".join(lines))

    # Error matches
    errors = context.get("error_matched_tickets", [])
    if errors:
        lines = ["PAST TICKETS WITH SAME ERROR:"]
        for t in errors[:3]:
            lines.append(f"  [{t['category']}] \"{t['title']}\" (error: {t.get('error_code', '?')})")
        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "No additional context available."


def _parse_llm_response(text: str) -> dict:
    """Parse JSON from LLM response."""
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()

    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse LLM response: %s", text[:200])
    return {}


async def classify_llm(
    title: str,
    description: str,
    context: RetrievalResult,
) -> dict:
    """
    Classify ticket using LLM with context.

    Returns:
        {
            "category": "Database",
            "priority": "high",
            "confidence": 0.94,
            "reasoning": "PostgreSQL connection issue..."
        }
    """
    context_text = _build_context_section(context)

    user_prompt = f"""{context_text}

NOW CLASSIFY THIS TICKET:
Title: {title}
Description: {description}

Return ONLY valid JSON: {{"category": "...", "priority": "...", "confidence": 0.0-1.0, "reasoning": "..."}}"""

    # Circuit breaker: fast-fail if Ollama is known to be down
    if not ollama_breaker.is_available:
        logger.warning("Circuit breaker OPEN — skipping Ollama call")
        return {"category": None, "confidence": 0.0, "reasoning": "Circuit breaker open — Ollama skipped"}

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
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        result = _parse_llm_response(content)

        valid_cats = {"Infrastructure", "Application", "Database", "Network", "Security", "Access Management"}
        valid_pris = {"critical", "high", "medium", "low"}

        category = result.get("category")
        if category not in valid_cats:
            category = None

        priority = result.get("priority", "medium")
        if priority not in valid_pris:
            priority = "medium"

        confidence = result.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        reasoning = result.get("reasoning", "")

        ollama_breaker.record_success()

        return {
            "category": category,
            "priority": priority,
            "confidence": round(confidence, 3),
            "reasoning": reasoning,
        }

    except httpx.ConnectError:
        ollama_breaker.record_failure()
        logger.warning("Ollama not reachable at %s (breaker: %s)", settings.OLLAMA_BASE_URL, ollama_breaker.state.value)
        return {"category": None, "confidence": 0.0, "reasoning": "Ollama unavailable"}
    except Exception as exc:
        ollama_breaker.record_failure()
        logger.error("LLM classification failed: %s (breaker: %s)", exc, ollama_breaker.state.value)
        return {"category": None, "confidence": 0.0, "reasoning": f"Error: {exc}"}
