# DeskMind — Solution Architecture Document

> **Nasscom Agentic AI Hackathon — Round 2 Submission**
> **Team**: Arif Asadullah, Aakarsh, Mohit Tomar
> **Date**: April 2026

---

## 1. Executive Summary

**DeskMind** is an AI-powered IT support ticket routing system that uses **GraphRAG** (Retrieval-Augmented Generation over a Knowledge Graph) to automatically classify, route, and suggest resolutions for IT support tickets.

**The Problem**: In enterprise IT operations, tickets are manually triaged by L1 support staff — a slow, error-prone process. Misrouted tickets add 2-4 hours of delay per incident, and critical issues get lost in queues.

**Our Solution**: DeskMind replaces manual triage with a **4-classifier ensemble** that:
- Classifies tickets into 6 IT domains using 4 independent AI classifiers
- Routes to the correct team with **90%+ confidence**
- Suggests resolutions from past similar incidents
- Recommends the best expert to handle the issue
- Gracefully degrades when components fail (never goes fully offline)

**What makes it different**: Unlike simple LLM-based classifiers, DeskMind combines **vector similarity search + knowledge graph traversal + error pattern matching + LLM reasoning** into a single pipeline. The knowledge graph captures infrastructure relationships (servers → services → teams → engineers → past incidents) that a standalone LLM cannot access.

---

## 2. High-Level Architecture

```
                                    ┌─────────────────────────────────────────┐
                                    │              DeskMind System            │
                                    └─────────────────────────────────────────┘

  ┌──────────┐     ┌──────────────────────────────────────────────────────────────────────┐
  │          │     │                        FastAPI Backend                                │
  │  React   │     │  ┌─────────┐   ┌──────────────────────────────────────────────────┐  │
  │ Frontend │────▶│  │   API   │──▶│          Classification Orchestrator             │  │
  │          │     │  │ Router  │   │                                                  │  │
  │ (Vite)   │     │  └─────────┘   │  ┌───────────┐  ┌───────────┐  ┌────────────┐  │  │
  │ Port 3000│     │                │  │  Stage 1   │  │  Stage 2   │  │  Stage 3   │  │  │
  └──────────┘     │                │  │  PREPARE   │─▶│  RETRIEVE  │─▶│  CLASSIFY  │  │  │
                   │                │  │            │  │            │  │            │  │  │
                   │                │  │- Entities  │  │- Vector    │  │- LLM (40%) │  │  │
                   │                │  │- Errors    │  │- Error     │  │- KNN (30%) │  │  │
                   │                │  │- Quality   │  │- Graph     │  │- Centroid  │  │  │
                   │                │  │- Embedding │  │- Fulltext  │  │  (20%)     │  │  │
                   │                │  └───────────┘  └───────────┘  │- Keyword   │  │  │
                   │                │                                │  (10%)     │  │  │
                   │                │  ┌───────────┐  ┌───────────┐  └────────────┘  │  │
                   │                │  │  Stage 5   │  │  Stage 4   │                 │  │
                   │                │  │  DECIDE    │◀─│  AGGREGATE │◀────────────────┘  │
                   │                │  │            │  │            │                    │
                   │                │  │- Route or  │  │- Weighted  │                    │
                   │                │  │  Escalate  │  │  Voting    │                    │
                   │                │  │- Team      │  │- Agreement │                    │
                   │                │  │- Expert    │  │- Calibrate │                    │
                   │                │  │- Runbook   │  │            │                    │
                   │                │  └───────────┘  └───────────┘                    │
                   │                └──────────────────────────────────────────────────┘  │
                   └──────────────────────────────┬──────────────────┬────────────────────┘
                                                  │                  │
                              ┌────────────────────┘                  └───────────────┐
                              │                                                       │
                   ┌──────────▼──────────┐    ┌──────────────┐    ┌──────────────────▼─┐
                   │     ArangoDB 3.12   │    │   Redis 7    │    │   Ollama (LLM)     │
                   │                     │    │              │    │                    │
                   │  - Document Store   │    │  - Health    │    │  - Qwen 2.5:3B    │
                   │  - Graph Engine     │    │    Cache     │    │  - Local inference │
                   │  - Vector Index     │    │  - Entity    │    │  - OpenAI-compat   │
                   │                     │    │    Cache     │    │    API             │
                   │  13 Doc Collections │    │              │    │                    │
                   │  9 Edge Collections │    │              │    │  Port 11434        │
                   │  1 Named Graph      │    │  Port 6379   │    │  (host machine)    │
                   │                     │    │              │    │                    │
                   │  Port 8530          │    └──────────────┘    └────────────────────┘
                   └─────────────────────┘
```

---

## 3. Solution Components

### 3.1 Frontend — React + Vite

| Component | File | Purpose |
|-----------|------|---------|
| Landing Page | `LandingPage.jsx` | Animated hero, live system status, "How it works" cards |
| Ticket Form | `App.jsx` | Submit ticket with title, description, priority |
| Ticket List | `TicketList.jsx` | Grid table with status, priority badges, team assignment |
| Chat AI | `ChatPanel.jsx` | Direct chat with LLM for ad-hoc queries |
| Status Bar | `StatusBar.jsx` | Real-time ArangoDB/Redis/Ollama health indicators |
| Splash Screen | `DeskMindSplash.jsx` | Animated brand intro (3.2s) |

**Design**: Neural Dark theme — `#0C0C0F` background, `#F97316` orange accent, glass-morphism cards.

### 3.2 Backend — FastAPI (Python)

#### API Layer

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/login` | POST | Public | Email + password → JWT access + refresh tokens |
| `/api/auth/register` | POST | Admin only | Create new user account linked to engineer/team |
| `/api/auth/refresh` | POST | Public (needs refresh token) | Exchange refresh token for new access token |
| `/api/auth/me` | GET | Any authenticated | Get current user info (role, team, email) |
| `/api/auth/users` | GET | Admin only | List all user accounts |
| `/api/auth/users/{email}/toggle-active` | PATCH | Admin only | Activate/deactivate a user |
| `/api/auth/bootstrap` | POST | Public (only when 0 users) | Create first admin account |
| `/api/auth/engineers` | GET | Admin only | List engineers with team info (for user creation form) |
| `/api/tickets` | POST | Any authenticated | Create + classify + route ticket |
| `/api/tickets` | GET | Any authenticated | List tickets (engineers: own team only) |
| `/api/tickets/{id}` | GET | Any authenticated | Get single ticket (engineers: own team only) |
| `/api/tickets/{id}/status` | PATCH | Engineer or Admin | Engineer picks up / reassigns / escalates (team-scoped) |
| `/api/tickets/{id}/resolve` | POST | Engineer or Admin | Close ticket with resolution steps (team-scoped) |
| `/api/tickets/{id}` | DELETE | Admin only | Delete a ticket |
| `/api/chat` | POST | Any authenticated | Direct LLM chat |
| `/health` | GET | Public | System health check |

#### Classification Pipeline (5 Stages)

**Stage 1 — PREPARE** (3 services):
- **Entity Extractor**: Scans ticket text for known server names (15), service names (12), error patterns (20). Caches entity lists from ArangoDB with 5-min TTL.
- **Error Scanner**: Maps matched error codes to categories for confidence bonus. Service-to-category mapping (e.g., `postgresql` → Database).
- **Quality Scorer**: Rates input as HIGH/MEDIUM/LOW based on text length + entity presence. Caps maximum confidence (HIGH=0.99, MEDIUM=0.85, LOW=0.75).

**Stage 2 — RETRIEVE** (4 parallel searches):
- **Vector Similarity**: Finds 5 most semantically similar past tickets using 384-dim MiniLM embeddings + ArangoDB vector index (cosine similarity).
- **Error Code Match**: Follows `triggered_by` edges from matched error codes to find past tickets with identical errors.
- **Graph Traversal**: Starting from mentioned server/service, follows `hosts` → `managed_by` → `affects` → `depends_on` → `member_of` edges to build infrastructure context.
- **Full-text Search**: Keyword index search on ticket descriptions for term-level matching.

**Stage 3 — CLASSIFY** (4 independent classifiers):

| Classifier | Weight | Method | Accuracy | Speed |
|-----------|--------|--------|----------|-------|
| LLM (Qwen 2.5:3B) | 0.40 | Reads ticket + all Stage 2 context, reasons about root cause | ~85% | ~2-5s |
| KNN Voting | 0.30 | Top 5 similar tickets vote by category (weighted by similarity) | ~80% | ~10ms |
| Centroid Distance | 0.20 | Compares embedding to 6 pre-computed category centroids | ~75% | ~5ms |
| Keyword Rules | 0.10 | 25+ keywords per category dictionary, count matches | ~55% | ~1ms |

**Stage 4 — AGGREGATE**:
- Weighted voting across all 4 classifiers
- Agreement bonus (+0.05 if 4/4 agree) or penalty (-0.10 if 1/4 disagree)
- Error code confirmation bonus (+0.03)
- Graph context confirmation bonus (+0.02)
- Confidence calibration based on agreement level
- Quality cap from Stage 1

**Stage 5 — DECIDE + ENRICH**:
- confidence >= 0.70 → Auto-route to team
- confidence < 0.70 → Escalate to human
- Attach: suggested resolution, recommended expert, matching runbook

#### Resolution Pipeline
- Finds best resolution from 3 sources: similar tickets, error-matched tickets, graph context (past tickets on same server)
- Ranks by effectiveness score (0.0-1.0)
- Matches runbooks by category
- Identifies expert from graph traversal (team member with relevant expertise)

#### Graceful Degradation

| Level | Condition | Available Classifiers | Weights | Expected Accuracy |
|-------|-----------|----------------------|---------|-------------------|
| 4 (Full) | All systems up | LLM + KNN + Centroid + Keywords | 0.40, 0.30, 0.20, 0.10 | ~90%+ |
| 3 (No Data) | Ollama up, DB empty | LLM + Keywords | 0.80, 0.20 | ~80% |
| 2 (No LLM) | Ollama down, DB up | KNN + Centroid + Keywords | 0.45, 0.35, 0.20 | ~70% |
| 1 (Emergency) | Ollama down, DB empty | Keywords only | 1.00 | ~55% |

Health checks run every 5 seconds (cached). The system never fully crashes — it always falls back to keyword classification.

### 3.3 Knowledge Graph — ArangoDB 3.12

ArangoDB serves as a **triple-purpose database**:
1. **Document Store** — tickets, teams, engineers, servers, services, resolutions, runbooks
2. **Graph Engine** — infrastructure relationships via 9 edge collections
3. **Vector Database** — 384-dim embeddings with APPROX_NEAR_COSINE similarity search

**13 Document Collections**: tickets, teams, engineers, servers, services, network_devices, error_codes, runbooks, resolutions, routing_rules, audit_log, category_centroids, users

**9 Edge Collections**: hosts, managed_by, depends_on, member_of, affects, assigned_to, resolved_with, references, triggered_by

**1 Named Graph**: `deskmind_graph` — connects all collections into a traversable knowledge graph

**Key Indexes**:
- Vector index on `tickets.embedding` (384 dimensions, cosine metric)
- Fulltext index on `tickets.description`
- Persistent indexes on frequently queried fields

### 3.4 Caching — Redis 7

- Health check results cached for 5 seconds
- Entity lists (servers, services, error codes) cached for 5 minutes
- Category centroids cached in-memory for 1 hour

### 3.5 LLM — Qwen 2.5:3B via Ollama

- **Model**: Qwen 2.5:3B (3 billion parameters)
- **Runtime**: Ollama (local inference, no cloud API calls)
- **API**: OpenAI-compatible chat completions endpoint
- **Purpose**: Primary classifier + chat interface
- **Prompt engineering**: Root-cause classification instruction with category definitions and context injection

---

## 4. Technology Stack

### Core Technologies

| Technology | Version | Role | Why We Chose It |
|-----------|---------|------|-----------------|
| **ArangoDB** | 3.12 CE | Knowledge Graph + Vector DB + Document Store | Only DB that natively combines graph, document, and vector search in one engine. Eliminates need for separate Neo4j + Pinecone + MongoDB. |
| **Qwen 2.5:3B** | 3B | Primary LLM Classifier | Best accuracy-to-size ratio for local inference. Runs on CPU without GPU. |
| **Ollama** | Latest | LLM Runtime | Local inference with OpenAI-compatible API. No cloud dependency, no API costs, full data privacy. |
| **MiniLM** | all-MiniLM-L6-v2 | Sentence Embeddings | 384-dim embeddings. Fast (<500ms per ticket), good semantic quality. Industry standard for similarity search. |
| **FastAPI** | Latest | Backend API | Async Python, auto-generated OpenAPI docs, Pydantic validation. Best performance for Python web APIs. |
| **React** | 19.1 | Frontend UI | Component-based, fast rendering, large ecosystem. |
| **Vite** | 6.3 | Frontend Build | Instant HMR, fast builds. Modern replacement for webpack. |
| **Redis** | 7 | Caching | In-memory speed for health checks, entity caching, and centroid caching. |
| **Docker Compose** | Latest | Orchestration | Single command to run all services. Consistent across dev environments (Mac + Windows team). |

### Python Libraries

| Library | Purpose |
|---------|---------|
| `sentence-transformers` | MiniLM embedding model loading and inference |
| `python-arango` | ArangoDB client (document CRUD + AQL queries + graph traversal) |
| `httpx` | Async HTTP client for Ollama API calls |
| `pydantic` + `pydantic-settings` | Request/response validation, environment config |
| `redis` | Redis async client |
| `spacy` | NLP text processing |
| `python-jose` | JWT token creation, signing, and validation for authentication |
| `passlib` | Bcrypt password hashing for secure credential storage |
| `python-dotenv` | Environment variable loading |

### Frontend Libraries

| Library | Purpose |
|---------|---------|
| `react` + `react-dom` | UI framework |
| `vite` | Build tooling + dev server with API proxy |

---

## 5. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Network                    │
│                        (atr-network)                         │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Frontend    │  │   Backend    │  │     ArangoDB 3.12   │ │
│  │  (React)     │  │  (FastAPI)   │  │                     │ │
│  │             │  │              │  │  Vector Index: ON    │ │
│  │  Port: 3000 │  │  Port: 8000  │  │  Port: 8530         │ │
│  │  Memory: -   │  │  Memory: -   │  │  Memory: 1GB        │ │
│  └──────┬──────┘  └──────┬───────┘  └─────────────────────┘ │
│         │                │                                    │
│         │          ┌─────┴──────┐    ┌─────────────────────┐ │
│         │          │  MiniLM    │    │     Redis 7         │ │
│         │          │  Embedding │    │                     │ │
│         │          │  Model     │    │  Port: 6379         │ │
│         │          │  (in-proc) │    │  Memory: 256MB      │ │
│         │          └────────────┘    └─────────────────────┘ │
│         │                                                     │
└─────────┼─────────────────────────────────────────────────────┘
          │
          │  host.docker.internal:11434
          │
┌─────────▼─────────────────┐
│     Ollama (Host Machine)  │
│                            │
│  Model: qwen2.5:3b         │
│  Port: 11434               │
│  Runs on: macOS / Linux    │
│  No GPU required           │
└────────────────────────────┘
```

**Why Ollama runs on the host**: Ollama needs direct access to the CPU/GPU. Running inside Docker adds overhead and complexity. The backend reaches Ollama via `host.docker.internal:11434`.

**Startup command**:
```bash
docker compose up --build -d    # Starts ArangoDB, Redis, Backend, Frontend
open /Applications/Ollama.app   # Start Ollama on Mac
python scripts/seed_db.py       # Load data (first time only, ~40 seconds)
```

---

## 6. Data Architecture

### Data Sources

| Source | Type | Records | Purpose |
|--------|------|---------|---------|
| `data/seed/seed_data.yaml` | Hand-crafted | 55 tickets, 6 teams, 15 servers, 12 services, 12 engineers, 20 error codes, 10 runbooks, 30 resolutions, 24 routing rules | Core knowledge graph — infrastructure topology, team structure, known error patterns |
| GPT-4o generated | AI-generated | 396 tickets | Diverse synthetic tickets across 6 categories |
| Claude hand-crafted | AI-generated | 191 tickets | High-quality edge cases and complex scenarios |
| Noise generator script | Programmatic | 200 tickets | Realistic noise: typos, abbreviations, truncation, irrelevant details |
| User submissions | Runtime | Growing | Real tickets submitted through the frontend |

### Data Pipeline

```
Seed YAML + Synthetic JSON
         │
         ▼
  scripts/seed_db.py
         │
         ├── Parse YAML/JSON
         ├── Compute 384-dim embeddings (MiniLM)
         ├── Insert documents (13 collections)
         ├── Create edges (9 edge collections)
         ├── Build vector indexes
         ├── Compute category centroids (avg embedding per category)
         └── Create named graph
         │
         ▼
  ArangoDB (1,795 documents, 3,831 edges)
         │
         ▼
  Ready for classification queries
```

### Data Numbers

| Metric | Count |
|--------|-------|
| Total documents | 1,795 |
| Total edges | 3,831 |
| Tickets (seed + synthetic) | 855 |
| Resolutions | 830 |
| Category centroids | 6 |
| Teams | 6 |
| Engineers | 12 |
| Servers | 15 |
| Services | 12 |
| Error codes | 20 |
| Runbooks | 10 |
| Routing rules | 24 |

---

## 7. Authentication & RBAC

DeskMind implements **JWT-based authentication** with **role-based access control (RBAC)** and **team-scoped data access**.

### Authentication Flow

```
User → Login (email + password) → Backend verifies bcrypt hash
    → Returns JWT access token (30 min) + refresh token (7 days)
    → Every API call includes: Authorization: Bearer <token>
    → Token expired? Frontend auto-refreshes silently
```

### 3 Roles

| Role | See Tickets | Create | Update Status | Resolve | Delete | Manage Users |
|------|------------|--------|--------------|---------|--------|-------------|
| **Admin** | All 6 domains | Yes | Yes (any team) | Yes (any team) | Yes | Yes |
| **Engineer** | Own team only | Yes | Yes (own team) | Yes (own team) | No | No |
| **Viewer** | All domains | Yes | No | No | No | No |

### Team-Scoped Access (the key feature)

Engineers are linked to teams via the knowledge graph:

```
users.team_key → teams._key → team domain
```

When an engineer calls `GET /api/tickets`, the backend filters to only return tickets where `routed_to` matches their team name. A Database Admin engineer sees only Database tickets. An Infrastructure engineer sees only Infrastructure tickets. Admins bypass this filter.

### Users Collection

A separate `users` collection stores authentication data (email, bcrypt password hash, role, team_key, is_active). This is deliberately separate from the `engineers` collection in the knowledge graph — auth accounts and domain knowledge entities have different lifecycles.

### User Management

Admins manage users through a dedicated UI page:
- Create new users (linked to engineers via `engineer_key`)
- Activate/deactivate accounts
- All user actions logged in audit trail

---

## 8. Security & Privacy

- **Local LLM**: All AI inference runs locally via Ollama. No ticket data leaves the network.
- **No cloud APIs**: After initial setup, the system operates fully offline.
- **JWT Authentication**: Stateless tokens with bcrypt password hashing. No plaintext passwords stored.
- **Team-scoped RBAC**: Engineers can only access their own team's tickets.
- **Audit trail**: Every classification decision and status change is logged with actor identity, confidence signals, and reasoning.
- **Data isolation**: User-submitted tickets are tagged `_source: "user"` and separated from training data.

---

## 9. Key Differentiators

| Feature | DeskMind | Typical AI Classifier |
|---------|----------|----------------------|
| Classification method | 4-classifier ensemble (LLM + KNN + Centroid + Keywords) | Single LLM call |
| Context retrieval | GraphRAG (vector + graph + error + fulltext) | Simple RAG (vector only) |
| Infrastructure awareness | Knowledge graph with server → service → team → engineer relationships | None |
| Failure handling | 4-level graceful degradation | Single point of failure |
| Confidence calibration | Agreement-based calibration + quality cap + contextual bonuses | Raw LLM logprobs |
| Resolution suggestion | 3-source resolution lookup + runbook matching + expert recommendation | None or basic |
| Data privacy | Fully local inference (Ollama) | Cloud API dependency |
| Explainability | Full audit trail with 4 classifier votes + reasoning | Black box |

---

## 10. Categories & Routing

DeskMind classifies tickets into **6 IT domains**:

| Category | Example Tickets | Target Team |
|----------|----------------|-------------|
| **Infrastructure** | Server down, disk full, K8s pod crash, CPU spike | Infrastructure Ops |
| **Application** | 502 errors, deployment failure, API timeout, memory leak | Application Support |
| **Database** | Connection refused, slow queries, replication lag, backup failure | Database Admin |
| **Network** | VPN issues, DNS resolution failure, firewall blocking, SSL cert expired | Network Operations |
| **Security** | Unauthorized access, brute force attack, certificate vulnerability | Security Operations |
| **Storage** | NFS mount failure, storage quota exceeded, backup corruption | Storage Engineering |

Each category has **4 routing rules** (critical/high/medium/low priority), totaling 24 rules that map `{category, priority}` → team.
