#!/usr/bin/env python3
"""
Generate 400 synthetic IT tickets using Phi-4-mini (local) + GPT-4o (API).
Each model generates 200 tickets across 3 personas.

Usage:
    python scripts/generate_tickets.py --openai-key sk-...
    python scripts/generate_tickets.py --phi-only          # skip GPT, Phi only
    python scripts/generate_tickets.py --gpt-only           # skip Phi, GPT only
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# ── Config ──
OUTPUT_DIR = Path("data/synthetic/strategy1_multimodel")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini")

CATEGORIES = ["Infrastructure", "Application", "Database", "Network", "Security", "Access Management"]
PRIORITIES = ["critical", "high", "medium", "low"]
PERSONAS = ["frustrated_user", "l2_engineer", "manager"]

# Category distribution per 25 tickets
CATEGORY_DIST = {
    "Infrastructure": 5,
    "Application": 5,
    "Database": 4,
    "Network": 4,
    "Security": 4,
    "Access Management": 3,
}

# Valid references from seed_data.yaml
VALID_SERVERS = [
    "prod-db-01", "prod-db-02", "prod-app-01", "prod-app-02", "prod-app-03",
    "prod-web-01", "prod-web-02", "prod-ldap-01", "prod-mail-01", "prod-mon-01",
    "prod-k8s-master", "prod-k8s-node-01", "prod-k8s-node-02", "prod-nfs-01", "staging-db-01"
]
VALID_SERVICES = [
    "postgresql", "redis", "nginx", "order-service", "auth-service", "api-gateway",
    "active-directory", "exchange", "prometheus", "kubernetes", "grafana", "nfs"
]
VALID_ERROR_CODES = [
    "ERR-SYS-001", "ERR-SYS-002", "ERR-SYS-003", "ERR-K8S-001",
    "ERR-NGINX-001", "ERR-NGINX-002", "ERR-APP-001",
    "ERR-PG-001", "ERR-PG-002", "ERR-PG-003", "ERR-REDIS-001",
    "ERR-DNS-001", "ERR-SSL-001", "ERR-VPN-001", "ERR-FW-001",
    "ERR-LDAP-001", "ERR-AUTH-001", "ERR-SEC-001",
    "ERR-NFS-001", "ERR-NFS-002"
]
VALID_RUNBOOKS = [
    "KB-0001", "KB-0002", "KB-0003", "KB-0004", "KB-0005",
    "KB-0006", "KB-0007", "KB-0008", "KB-0009", "KB-0010", None
]

# ── Persona Prompts ──
PERSONA_INSTRUCTIONS = {
    "frustrated_user": """You are writing as a FRUSTRATED END USER who is not technical.
Style: emotional, messy, incomplete sentences, typos allowed, uses ALL CAPS for emphasis.
Example: "HELP!! email not loading… meeting in 10 min… tried chrome edge same issue pls fix asap"
- Short, panicked descriptions (2-4 sentences)
- No technical details, just symptoms
- May mention wrong service names or vague terms
- Priority should feel urgent from their perspective""",

    "l2_engineer": """You are writing as an L2 SUPPORT ENGINEER who is very technical.
Style: structured, includes timestamps, log snippets, error codes, server names, metrics.
Example: "prod-db-02 error FATAL: too many connections at 2026-04-14T03:22Z. Pool exhausted (47/50). Suspect connection leak after deploy CHG-8834. max_connections=50 in postgresql.conf."
- Detailed technical descriptions (3-6 sentences)
- Includes specific server names, ports, error messages
- References recent changes or deploys
- Includes metrics and thresholds""",

    "manager": """You are writing as a BUSINESS MANAGER who focuses on impact, not technical details.
Style: professional, business-focused, mentions team/revenue/deadline impact.
Example: "Sales team cannot access CRM since this morning. This is impacting our quarterly close — 15 reps are idle. Please provide ETA and escalate if needed."
- Business impact focused (2-4 sentences)
- Mentions affected teams, customers, or revenue
- Asks for ETA or escalation
- Vague on technical details"""
}

SYSTEM_PROMPT = """You are a synthetic IT ticket generator for DeskMind, an AI ticket routing system.

Generate exactly {count} unique IT support tickets as a JSON array.

RULES:
1. Each ticket must be UNIQUE — no duplicate titles or similar descriptions
2. Classify by ROOT CAUSE, not symptom
3. Use ONLY these valid references:
   - servers: {servers}
   - services: {services}
   - error_codes: {error_codes} (use only when the ticket description contains that error)
   - runbooks: {runbooks} (use null if no runbook applies, ~60% should be null)

CATEGORY DISTRIBUTION for {count} tickets:
{category_dist}

PERSONA:
{persona_instruction}

OUTPUT FORMAT — return ONLY a valid JSON array, no other text:
[
  {{
    "title": "short descriptive title",
    "description": "ticket description matching the persona style",
    "category": "one of: Infrastructure, Application, Database, Network, Security, Access Management",
    "priority": "one of: critical, high, medium, low",
    "affects_servers": ["server-name"] or [],
    "affects_services": ["service-name"] or [],
    "error_codes": ["ERR-XX-XXX"] or [],
    "resolution_steps": ["step 1", "step 2", "step 3"],
    "resolution_effectiveness": 0.7 to 1.0,
    "references_runbook": "KB-XXXX" or null
  }}
]

IMPORTANT: Return ONLY the JSON array. No markdown, no explanation, no ```json tags."""


def build_prompt(persona: str, count: int, existing_titles: list[str] = None) -> str:
    """Build the generation prompt for a specific persona."""
    # Build category distribution string
    dist_str = "\n".join(f"  {cat}: {n}" for cat, n in CATEGORY_DIST.items())
    # Scale distribution to requested count
    scale = count / 25
    scaled_dist = "\n".join(f"  {cat}: {int(n * scale)}" for cat, n in CATEGORY_DIST.items())

    prompt = SYSTEM_PROMPT.format(
        count=count,
        servers=", ".join(VALID_SERVERS),
        services=", ".join(VALID_SERVICES),
        error_codes=", ".join(VALID_ERROR_CODES),
        runbooks=", ".join(str(r) for r in VALID_RUNBOOKS if r),
        category_dist=scaled_dist,
        persona_instruction=PERSONA_INSTRUCTIONS[persona],
    )

    if existing_titles:
        prompt += f"\n\nTitles already used (DO NOT repeat any of these):\n"
        for t in existing_titles[-50:]:  # last 50 to avoid huge prompts
            prompt += f"- {t}\n"

    return prompt


def call_ollama(prompt: str, model: str = None) -> str:
    """Call local Ollama API."""
    model = model or OLLAMA_MODEL
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(
            f"{OLLAMA_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI GPT-4o API."""
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a JSON generator. Return only valid JSON arrays. No markdown, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 16000,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def parse_json_response(text: str) -> list[dict]:
    """Extract JSON array from LLM response (handles markdown wrapping)."""
    text = text.strip()
    # Remove markdown code blocks if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try parsing as array
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "tickets" in data:
            return data["tickets"]
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    print(f"  WARNING: Could not parse JSON response. First 200 chars: {text[:200]}")
    return []


def validate_ticket(ticket: dict) -> bool:
    """Validate a generated ticket has required fields and valid references."""
    required = ["title", "description", "category", "priority"]
    for field in required:
        if field not in ticket or not ticket[field]:
            return False

    if ticket["category"] not in CATEGORIES:
        return False
    if ticket["priority"] not in PRIORITIES:
        return False

    # Ensure list fields are lists (LLM may return None)
    for field in ["affects_servers", "affects_services", "error_codes", "resolution_steps"]:
        if not isinstance(ticket.get(field), list):
            ticket[field] = []

    # Validate server references
    ticket["affects_servers"] = [s for s in ticket["affects_servers"] if s in VALID_SERVERS]

    # Validate service references
    ticket["affects_services"] = [s for s in ticket["affects_services"] if s in VALID_SERVICES]

    # Validate error codes
    ticket["error_codes"] = [e for e in ticket["error_codes"] if e in VALID_ERROR_CODES]

    # Validate runbook
    if ticket.get("references_runbook") and ticket["references_runbook"] not in [r for r in VALID_RUNBOOKS if r]:
        ticket["references_runbook"] = None

    return True


def generate_batch(
    model_name: str,
    call_fn,
    persona: str,
    batch_size: int,
    existing_titles: list[str],
    batch_num: int,
    total_batches: int,
) -> list[dict]:
    """Generate one batch of tickets."""
    print(f"  [{batch_num}/{total_batches}] {model_name} / {persona} / {batch_size} tickets...")

    prompt = build_prompt(persona, batch_size, existing_titles)

    try:
        response = call_fn(prompt)
        tickets = parse_json_response(response)
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

    # Validate and tag each ticket
    valid = []
    for ticket in tickets:
        if validate_ticket(ticket):
            ticket["source_model"] = model_name
            ticket["persona"] = persona
            ticket.setdefault("affects_servers", [])
            ticket.setdefault("affects_services", [])
            ticket.setdefault("error_codes", [])
            ticket.setdefault("resolution_steps", [])
            ticket.setdefault("resolution_effectiveness", 0.85)
            ticket.setdefault("references_runbook", None)
            ticket.setdefault("quality_score", "HIGH")
            ticket.setdefault("secondary_category", None)
            ticket.setdefault("classifier_votes", None)
            valid.append(ticket)

    print(f"    Generated: {len(tickets)}, Valid: {len(valid)}")
    return valid


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic IT tickets")
    parser.add_argument("--openai-key", help="OpenAI API key for GPT-4o")
    parser.add_argument("--phi-only", action="store_true", help="Generate Phi-4-mini tickets only")
    parser.add_argument("--gpt-only", action="store_true", help="Generate GPT-4o tickets only")
    parser.add_argument("--batch-size", type=int, default=25, help="Tickets per batch (default: 25)")
    parser.add_argument("--tickets-per-model", type=int, default=200, help="Total tickets per model (default: 200)")
    args = parser.parse_args()

    if args.gpt_only and not args.openai_key:
        print("ERROR: --openai-key required with --gpt-only")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_titles = []
    total_generated = 0

    # ── Phi-4-mini ──
    if not args.gpt_only:
        print("\n=== Generating with Phi-4-mini (local) ===")
        phi_tickets = []
        tickets_per_persona = args.tickets_per_model // 3
        batch_num = 0
        total_batches = (args.tickets_per_model // args.batch_size) or 1

        for persona in PERSONAS:
            remaining = tickets_per_persona
            while remaining > 0:
                batch_size = min(args.batch_size, remaining)
                batch_num += 1
                batch = generate_batch(
                    model_name="phi4-mini",
                    call_fn=lambda p: call_ollama(p),
                    persona=persona,
                    batch_size=batch_size,
                    existing_titles=all_titles,
                    batch_num=batch_num,
                    total_batches=total_batches,
                )
                phi_tickets.extend(batch)
                all_titles.extend(t["title"] for t in batch)
                remaining -= len(batch)
                if not batch:
                    print("  Retrying...")
                    time.sleep(2)

        # Save Phi tickets
        output_file = OUTPUT_DIR / "phi4_tickets.json"
        with open(output_file, "w") as f:
            json.dump(phi_tickets, f, indent=2)
        print(f"\nPhi-4-mini: {len(phi_tickets)} tickets saved to {output_file}")
        total_generated += len(phi_tickets)

    # ── GPT-4o ──
    if not args.phi_only and args.openai_key:
        print("\n=== Generating with GPT-4o (API) ===")
        gpt_tickets = []
        tickets_per_persona = args.tickets_per_model // 3
        batch_num = 0
        total_batches = (args.tickets_per_model // args.batch_size) or 1

        for persona in PERSONAS:
            remaining = tickets_per_persona
            while remaining > 0:
                batch_size = min(args.batch_size, remaining)
                batch_num += 1
                batch = generate_batch(
                    model_name="gpt-4o",
                    call_fn=lambda p: call_openai(p, args.openai_key),
                    persona=persona,
                    batch_size=batch_size,
                    existing_titles=all_titles,
                    batch_num=batch_num,
                    total_batches=total_batches,
                )
                gpt_tickets.extend(batch)
                all_titles.extend(t["title"] for t in batch)
                remaining -= len(batch)
                if not batch:
                    print("  Retrying after 5s...")
                    time.sleep(5)

        # Save GPT tickets
        output_file = OUTPUT_DIR / "gpt4o_tickets_batch2.json"
        with open(output_file, "w") as f:
            json.dump(gpt_tickets, f, indent=2)
        print(f"\nGPT-4o: {len(gpt_tickets)} tickets saved to {output_file}")
        total_generated += len(gpt_tickets)

    print(f"\n=== Total generated: {total_generated} tickets ===")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Next: Generate Claude tickets (200) and noise tickets (200)")


if __name__ == "__main__":
    main()
