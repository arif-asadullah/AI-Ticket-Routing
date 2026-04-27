#!/usr/bin/env python3
"""
Generate 200 synthetic IT tickets using templates + programmatic noise.
No LLM required — pure Python string manipulation.

Usage:
    python scripts/generate_noise_tickets.py
"""

import json
import random
import string
from pathlib import Path

OUTPUT_DIR = Path("data/synthetic/strategy2_noise")

# ── Templates per category ──
TEMPLATES = {
    "Infrastructure": [
        "{server} CPU usage at {pct}% for {duration}. {service} response times degraded.",
        "Kernel panic on {server}. Server rebooted unexpectedly. {impact}",
        "Disk space {pct}% on {server}. {service} logs filling up. {urgency}",
        "Docker daemon not responding on {server}. All containers inaccessible.",
        "Memory usage at {pct}% on {server}. OOM killer activated. {impact}",
        "{server} unreachable via SSH and ping. {impact}",
        "Ubuntu security patch failed on {server}. apt-get stuck. {urgency}",
        "Kubernetes pod CrashLoopBackOff on {server}. {service} affected.",
    ],
    "Application": [
        "{service} returning {error_code} errors on {server}. {impact}",
        "{service} timeout on {endpoint}. Response time {latency}ms. {urgency}",
        "Deployment {version} failed on {server}. Rollback needed. {impact}",
        "{service} throwing NullPointerException in {module}. {pct}% of requests failing.",
        "JWT token validation failing on {service}. All auth calls rejected.",
        "{service} memory leak — heap growing {rate}MB per hour. {urgency}",
        "Config syntax error in {service} after update. {impact}",
        "Health check endpoint returning 500 on {server}. Load balancer marking it down.",
    ],
    "Database": [
        "PostgreSQL not accepting connections on {server}. {error_code}. {impact}",
        "Replication lag {latency}s between {server} and {server2}. {urgency}",
        "Slow queries on {server} blocking production. Query time {latency}ms. {impact}",
        "Redis OOM on {server}. Used memory {pct}% of maxmemory. {urgency}",
        "Backup job failed on {server}. Incomplete backup file. {impact}",
        "Database migration script failed on {server}. Schema inconsistent.",
        "Connection pool exhausted on {server}. {error_code}. {urgency}",
        "Deadlock detected on {server}. {pct}% of transactions failing.",
    ],
    "Network": [
        "VPN connection dropping every {duration}. {error_code}. {impact}",
        "DNS resolution failing for internal services. {urgency}",
        "Firewall {device} blocking traffic to {server} on port {port}. {impact}",
        "Load balancer health check failing for {server}. Traffic on single server.",
        "High latency {latency}ms between datacenters. {impact}",
        "SSL certificate expired on {service}. {error_code}. {urgency}",
        "Packet loss {pct}% on {device}. {impact}",
        "BGP peering down with ISP on {device}. Backup routing active.",
    ],
    "Security": [
        "{count} failed login attempts on admin account from {ip}. {urgency}",
        "User locked out after password change. {error_code}. {impact}",
        "Vulnerability scan found critical CVE on {server}. {urgency}",
        "Unauthorized SSH access attempt on {server} from {ip}. {impact}",
        "Service account token expired on {service}. All API calls rejected.",
        "TLS certificate mismatch on {service}. {impact}",
        "Privilege escalation attempt detected on {server}. {urgency}",
        "Phishing email reported by {count} employees. {impact}",
    ],
    "Storage": [
        "NFS mount failing on {server}. {error_code}. {impact}",
        "Stale NFS file handle on {server}. Multiple servers affected. {urgency}",
        "Backup storage quota exceeded on {server}. Last {count} backups failed.",
        "NFS server {server} not responding. All clients hung. {impact}",
        "SAN LUN mapping incorrect on {server} after firmware update. {urgency}",
        "File system corruption on {server}. Read-only mode. {impact}",
        "RAID array degraded on {server}. One disk failed. {urgency}",
        "Disk I/O latency {latency}ms on {server}. {service} affected.",
    ],
}

# ── Fill values ──
SERVERS = ["prod-db-01", "prod-db-02", "prod-app-01", "prod-app-02", "prod-app-03",
           "prod-web-01", "prod-web-02", "prod-ldap-01", "prod-mail-01", "prod-mon-01",
           "prod-k8s-master", "prod-k8s-node-01", "prod-k8s-node-02", "prod-nfs-01", "staging-db-01"]
SERVICES = ["order-service", "auth-service", "nginx", "postgresql", "redis",
            "api-gateway", "prometheus", "grafana", "kubernetes", "exchange", "nfs"]
DEVICES = ["fw-prod-01", "fw-prod-02", "sw-core-01", "lb-web-01", "vpn-gw-01"]
ERROR_CODES = ["ERR-PG-001", "ERR-NGINX-001", "ERR-K8S-001", "ERR-NFS-001",
               "ERR-SSL-001", "ERR-VPN-001", "ERR-REDIS-001", "ERR-SYS-002"]
IMPACTS = [
    "Users reporting issues", "Customer checkout broken", "Team unable to work",
    "Revenue impact estimated", "On-call team notified", "Multiple teams affected",
    "Monitoring alerts firing", "SLA at risk", "Management escalation imminent",
]
URGENCIES = [
    "Please fix ASAP", "Needs immediate attention", "Critical for business",
    "Blocking deployment", "Affecting production", "Customers complaining",
]
ENDPOINTS = ["/api/orders", "/api/users", "/api/auth", "/health", "/api/checkout", "/api/reports"]
MODULES = ["PaymentGateway", "OrderProcessor", "AuthHandler", "CacheManager", "ReportGenerator"]
VERSIONS = ["v2.3.1", "v2.4.0", "v3.0.0-rc1", "v2.3.5", "v1.8.2"]
IPS = ["10.0.2.15", "203.0.113.42", "192.168.1.100", "10.0.5.22", "172.16.0.50"]

# ── Noise injection ──
TYPOS = {
    "please": ["plese", "pls", "plz", "pleaase"],
    "server": ["servr", "sever", "serber"],
    "error": ["eror", "errror", "err"],
    "database": ["databse", "db", "databade"],
    "connection": ["conection", "connexion", "conn"],
    "environment": ["envrionment", "env", "envirnoment"],
    "production": ["prod", "prodction", "producton"],
    "immediately": ["immediatly", "asap", "right now!!"],
}
PRIORITIES = ["critical", "high", "medium", "low"]

IRRELEVANT = [
    " (my laptop is Dell btw)",
    " — using Chrome on Mac",
    "\nNote: I'm working from home today",
    " [sent from iPhone]",
    "\n\nAlso, unrelated but can someone reset my password?",
    " — this is urgent because my manager asked",
]


def inject_noise(text: str) -> str:
    """Add typos, abbreviations, and irrelevant info."""
    # Random typos (30% chance per word)
    for word, replacements in TYPOS.items():
        if word in text.lower() and random.random() < 0.3:
            text = text.replace(word, random.choice(replacements), 1)

    # Random irrelevant info (20% chance)
    if random.random() < 0.2:
        text += random.choice(IRRELEVANT)

    # Random ALL CAPS for a sentence (15% chance)
    if random.random() < 0.15:
        sentences = text.split(". ")
        if sentences:
            idx = random.randint(0, len(sentences) - 1)
            sentences[idx] = sentences[idx].upper()
            text = ". ".join(sentences)

    # Random extra punctuation (10% chance)
    if random.random() < 0.1:
        text = text.replace(".", "!!!")
        text = text.replace("!", "!!!")

    return text


def generate_ticket(category: str, ticket_num: int) -> dict:
    """Generate one noisy ticket from templates."""
    template = random.choice(TEMPLATES[category])

    server = random.choice(SERVERS)
    server2 = random.choice([s for s in SERVERS if s != server])
    service = random.choice(SERVICES)
    device = random.choice(DEVICES)

    description = template.format(
        server=server,
        server2=server2,
        service=service,
        device=device,
        pct=random.randint(85, 100),
        duration=random.choice(["10 minutes", "30 minutes", "1 hour", "2 hours", "since morning"]),
        latency=random.choice([200, 500, 1000, 5000, 15000, 30000]),
        impact=random.choice(IMPACTS),
        urgency=random.choice(URGENCIES),
        error_code=random.choice(ERROR_CODES),
        endpoint=random.choice(ENDPOINTS),
        module=random.choice(MODULES),
        version=random.choice(VERSIONS),
        rate=random.randint(50, 200),
        port=random.choice([443, 5432, 8080, 6379, 389]),
        count=random.randint(3, 50),
        ip=random.choice(IPS),
    )

    # Apply noise
    description = inject_noise(description)

    # Generate title (shorter, sometimes noisy)
    title_templates = {
        "Infrastructure": [f"{server} down", f"CPU high on {server}", f"Disk full {server}", f"{server} not responding"],
        "Application": [f"{service} 502 errors", f"{service} timeout", f"Deploy failed {service}", f"{service} crashing"],
        "Database": [f"PostgreSQL connection issue", f"Redis OOM {server}", f"DB slow queries", f"Replication lag"],
        "Network": [f"VPN dropping", f"Firewall blocking {server}", f"DNS failing", f"SSL expired"],
        "Security": [f"Failed login attempts", f"User locked out", f"CVE found on {server}", f"Unauthorized access"],
        "Storage": [f"NFS mount failing", f"Disk I/O slow {server}", f"RAID degraded {server}", f"Storage full"],
    }
    title = random.choice(title_templates[category])
    if random.random() < 0.3:
        title = inject_noise(title)

    # Determine affected servers/services
    affects_servers = [server] if server in SERVERS else []
    affects_services = []
    for svc in SERVICES:
        if svc in description.lower():
            affects_services.append(svc)

    # Match error codes
    matched_errors = []
    for err in ERROR_CODES:
        if err in description:
            matched_errors.append(err)

    # Simple resolution
    resolution_templates = [
        [f"Checked {server} status", f"Identified root cause", f"Applied fix", f"Verified resolution"],
        [f"SSHed into {server}", f"Restarted {service}", f"Monitored for 30 minutes"],
        [f"Investigated logs on {server}", f"Found configuration issue", f"Updated config", f"Restarted service"],
    ]

    return {
        "title": title,
        "description": description,
        "category": category,
        "priority": random.choices(PRIORITIES, weights=[15, 35, 35, 15])[0],
        "affects_servers": affects_servers,
        "affects_services": affects_services[:2],
        "error_codes": matched_errors[:1],
        "resolution_steps": random.choice(resolution_templates),
        "resolution_effectiveness": round(random.uniform(0.70, 0.95), 2),
        "references_runbook": random.choice(VALID_RUNBOOKS) if random.random() < 0.3 else None,
        "quality_score": "HIGH",
        "secondary_category": None,
        "classifier_votes": None,
        "source_model": "template_noise",
        "persona": random.choice(["frustrated_user", "l2_engineer", "manager"]),
    }


VALID_RUNBOOKS = ["KB-0001", "KB-0002", "KB-0003", "KB-0004", "KB-0005",
                  "KB-0006", "KB-0007", "KB-0008", "KB-0009", "KB-0010"]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(42)  # reproducible

    tickets = []
    # Distribution: 200 tickets across 6 categories
    dist = {"Infrastructure": 40, "Application": 38, "Database": 34, "Network": 32, "Security": 30, "Storage": 26}

    ticket_num = 0
    for category, count in dist.items():
        for i in range(count):
            ticket_num += 1
            ticket = generate_ticket(category, ticket_num)
            tickets.append(ticket)

    random.shuffle(tickets)

    output_file = OUTPUT_DIR / "noise_tickets.json"
    with open(output_file, "w") as f:
        json.dump(tickets, f, indent=2)

    print(f"Generated {len(tickets)} noise tickets")
    print(f"Saved to {output_file}")

    # Stats
    cats = {}
    for t in tickets:
        cats[t["category"]] = cats.get(t["category"], 0) + 1
    print(f"\nCategory distribution:")
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
