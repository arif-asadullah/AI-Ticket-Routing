# DeskMind Architecture

This folder explains **how DeskMind's AI routing works** — from the moment a user submits a ticket to when it gets routed to the right team with a suggested fix.

If you're new to AI, vectors, or graph databases — this is written for you. Every concept is explained from scratch with real-world analogies.

## What DeskMind Does (in one sentence)

DeskMind reads an IT support ticket, **understands what the problem is**, finds **similar past problems and their solutions**, and **routes the ticket to the correct team** — all automatically.

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER SUBMITS TICKET                        │
│  "PostgreSQL not accepting connections on prod-db-01"           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 1: UNDERSTAND                            │
│                                                                 │
│  Convert ticket text → 384 numbers (embedding)                  │
│  Extract entities: "PostgreSQL", "prod-db-01"                   │
│  Match error patterns: "too many connections" = ERR-PG-001      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 2: SEARCH (3 methods)                   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐        │
│  │Vector Search │  │Error Pattern │  │Graph Traversal │        │
│  │              │  │  Matching    │  │                │        │
│  │Find tickets  │  │Find tickets  │  │Find tickets on │        │
│  │with similar  │  │with same     │  │same server or  │        │
│  │MEANING       │  │ERROR CODE    │  │same service    │        │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘        │
│         │                 │                   │                 │
│         └─────────┬───────┘                   │                 │
│                   │                           │                 │
│                   ▼                           ▼                 │
│         Candidate past tickets + their resolutions              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 3: CLASSIFY (LLM)                       │
│                                                                 │
│  Qwen 2.5:7B reads:                                              │
│  - The new ticket description                                   │
│  - 5 similar past tickets with their resolutions                │
│  - Graph context (what server, what service, who manages it)    │
│                                                                 │
│  Returns:                                                       │
│  {                                                              │
│    category: "Database",                                        │
│    priority: "high",                                            │
│    confidence: 0.95,                                            │
│    reasoning: "PostgreSQL connection issue..."                  │
│  }                                                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 4: ROUTE                                │
│                                                                 │
│  confidence >= 0.70?                                            │
│    YES → Route to Database Admin team (SLA: 4 hours)            │
│    NO  → Escalate to human for manual triage                    │
│                                                                 │
│  Suggested resolution: "Increase max_connections (KB-0001)"     │
│  Recommended engineer: Arjun Nair (PostgreSQL expert)           │
└─────────────────────────────────────────────────────────────────┘
```

## What's in Each Document

| Document | What it explains | Read this if... |
|----------|-----------------|-----------------|
| [vector-search.md](vector-search.md) | How the AI finds similar tickets by meaning, not keywords. What embeddings are, how cosine similarity works. | You want to understand "how does the AI know two tickets are about the same problem?" |
| [graph-traversal.md](graph-traversal.md) | How the knowledge graph connects servers, services, teams, and tickets. How the AI follows edges to find context. | You want to understand "how does the AI know which server runs which service and who manages it?" |
| [error-matching.md](error-matching.md) | How known error patterns (like "FATAL: too many connections") are matched instantly without AI. | You want to understand "how does the system recognize error codes?" |
| [classification-pipeline.md](classification-pipeline.md) | 4-classifier ensemble: LLM + KNN + Centroid + Keywords. Weighted voting, confidence calibration, graceful degradation. | You want to understand "how does everything work together end-to-end?" |

## Technologies Used

| Technology | Role in DeskMind | Analogy |
|-----------|-----------------|---------|
| **ArangoDB** | Stores everything — tickets, servers, teams, resolutions, and the graph connections between them | A filing cabinet that also understands how the files are related to each other |
| **Qwen 2.5:7B (Ollama)** | The AI brain — reads tickets, understands them, classifies them | A very fast junior IT analyst who can read and categorize tickets |
| **MiniLM (sentence-transformers)** | Converts text into numbers (embeddings) so we can compare ticket meanings mathematically | A translator that converts English into "meaning coordinates" |
| **Redis** | Caches frequent results so the same ticket type doesn't need re-processing | A sticky note on your desk with answers to frequently asked questions |
| **FastAPI** | The backend server that receives tickets and returns routing decisions | The reception desk that receives tickets and sends them to the right department |
| **React** | The frontend UI where users submit tickets and see results | The website where users interact with the system |

## The 6 Categories

Every ticket is classified into one of these:

| Category | What it covers | Routed to |
|----------|---------------|-----------|
| **Infrastructure** | Servers, VMs, OS, CPU, RAM, disk, hardware | Infrastructure Ops |
| **Application** | App crashes, API errors, deployments, bugs | Application Support |
| **Database** | SQL, connections, replication, backups | Database Admin |
| **Network** | DNS, firewall, VPN, latency, load balancer | Network Engineering |
| **Security** | Auth, certificates, vulnerabilities, access | Security Ops |
| **Access Management** | LDAP, Active Directory, SSO, SAML, OAuth, MFA, RBAC, permissions, account lockouts | Access Management |

## Reading Order

If you're completely new, read in this order:
1. **This file** (you're here) — the big picture
2. **vector-search.md** — understand the AI's core search mechanism
3. **error-matching.md** — understand the fast shortcut
4. **graph-traversal.md** — understand how infrastructure context helps
5. **classification-pipeline.md** — the 4-classifier ensemble pipeline (the full picture)
