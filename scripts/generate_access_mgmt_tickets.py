#!/usr/bin/env python3
"""
Generate Access Management tickets using GPT-4o with 3 personas.

Persona A: Frustrated end user (typos, abbreviations, non-technical)
Persona B: L2 engineer (precise, includes logs, error codes, hostnames)
Persona C: Vague manager (formal, business impact, no technical details)
"""

import json
import os
import time

import httpx

API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = "gpt-4o"
OUTPUT_FILE = "data/synthetic/access_mgmt_gpt4o.json"

SYSTEM_PROMPT = """You are generating realistic IT support tickets for the "Access Management" domain.

Access Management covers: LDAP, Active Directory, SSO (Single Sign-On), SAML, OAuth, MFA (Multi-Factor Authentication), RBAC (Role-Based Access Control), user provisioning/deprovisioning, password policies, account lockouts, group memberships, identity governance, service accounts, access reviews, certificate-based authentication, federation, directory replication.

Each ticket must be a JSON object with these fields:
- title: short summary (5-15 words)
- description: detailed problem description (50-200 words)
- category: always "Access Management"
- priority: one of "critical", "high", "medium", "low"
- error_codes: list of realistic error patterns (can be empty)
- server_names: list of server hostnames mentioned (can be empty)
- service_names: list of services mentioned (can be empty)

Return a JSON array of tickets. No markdown, no code blocks, just the JSON array."""

PERSONA_PROMPTS = {
    "frustrated_user": {
        "count": 14,
        "prompt": """Generate {count} Access Management support tickets written by a FRUSTRATED END USER.

Style: stressed, non-technical, incomplete sentences, typos, abbreviations (pls, asap, env, cant, doesnt), describes symptoms not system names. Uses "!!!" and CAPS for urgency. Doesn't know the technical cause.

Examples of topics: can't login, locked out, password reset not working, new hire can't access anything, lost MFA device, permissions changed randomly, SSO keeps logging me out, shared account not working."""
    },
    "l2_engineer": {
        "count": 14,
        "prompt": """Generate {count} Access Management support tickets written by an L2 ENGINEER pasting logs.

Style: precise, includes hostnames (prod-ldap-01), timestamps, error codes, log snippets, LDAP error codes (e.g., LDAP error 49, 52e, 525, 701, 773), AD Event IDs (4740, 4771, 4625), SAML error traces. Very technical.

Examples of topics: AD replication USN mismatch, LDAP bind failures from specific service accounts, Kerberos ticket renewal failures, SAML assertion signature mismatch, Azure AD Connect sync errors, group policy not applying, SID history migration issues."""
    },
    "vague_manager": {
        "count": 12,
        "prompt": """Generate {count} Access Management support tickets written by a VAGUE MANAGER escalating an issue.

Style: formal, describes business impact, no technical details, urgency language ("revenue impact", "customer-facing", "board meeting", "audit deadline"). Doesn't know which server or service is involved. Uses phrases like "my team", "the system", "it stopped working".

Examples of topics: team can't access reports before board meeting, new department can't use any tools, compliance audit failing because access reviews incomplete, contractor access not revoked after project ended, VIP executive locked out."""
    },
}


def generate_batch(persona_name: str, persona_config: dict) -> list:
    """Generate tickets for one persona via GPT-4o."""
    count = persona_config["count"]
    prompt = persona_config["prompt"].format(count=count)

    print(f"  Generating {count} tickets ({persona_name})...")

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 8000,
        },
        timeout=120.0,
    )

    if resp.status_code != 200:
        print(f"    ERROR: {resp.status_code} — {resp.text[:200]}")
        return []

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Parse JSON — handle markdown code blocks
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        tickets = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"    ERROR parsing JSON: {e}")
        print(f"    Raw content: {content[:300]}...")
        return []

    # Tag each ticket
    for t in tickets:
        t["category"] = "Access Management"
        t["_source"] = "synthetic"
        t["_generator"] = f"gpt-4o-{persona_name}"

    print(f"    Got {len(tickets)} tickets")
    return tickets


def main():
    if not API_KEY:
        print("ERROR: Set OPENAI_API_KEY environment variable")
        return

    print(f"Generating Access Management tickets via {MODEL}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    all_tickets = []

    for persona_name, persona_config in PERSONA_PROMPTS.items():
        tickets = generate_batch(persona_name, persona_config)
        all_tickets.extend(tickets)
        time.sleep(2)  # Rate limit

    print(f"\nTotal: {len(all_tickets)} tickets generated")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_tickets, f, indent=2)

    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
