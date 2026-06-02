# DeskMind — Solution Architecture Document

> **Nasscom AI-Code-Sarathi Excel Hackathon — Final Round (Jury)**
> **Team**: Arif Asadullah, Aakarsh, Mohit Tomar
> **Date**: June 2026 (updated from R2 submission)

---

## 1. Executive Summary

**DeskMind** is an AI-powered IT support ticket routing system that uses **GraphRAG** (Retrieval-Augmented Generation over a Knowledge Graph) to automatically classify, route, and suggest resolutions for IT support tickets.

**The Problem**: In enterprise IT operations, tickets are manually triaged by L1 support staff — a slow, error-prone process. Misrouted tickets add 2-4 hours of delay per incident, and critical issues get lost in queues.

**Our Solution**: DeskMind replaces manual triage with a **4-classifier ensemble** that:
- Classifies tickets into 6 IT domains using 4 independent AI classifiers (**94.1% accuracy**, benchmark-verified)
- Routes to the correct team with high confidence
- **Generates custom AI resolutions** grounded in past incidents + knowledge graph (not just retrieves)
- Detects incidents proactively (cluster, trend, spike detection)
- Enriches vague tickets with intelligent follow-up questions
- Recommends the best expert to handle the issue
- Gracefully degrades when components fail (never goes fully offline)

**What makes it different**: Unlike simple LLM-based classifiers, DeskMind combines **vector similarity search + knowledge graph traversal + error pattern matching + LLM reasoning** into a single pipeline. The knowledge graph captures infrastructure relationships (servers → services → teams → engineers → past incidents) that a standalone LLM cannot access. The system is **truly agentic** — it doesn't just classify tickets, it generates resolutions, predicts incidents, and learns from corrections.

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
                   │  - Document Store   │    │  - 2-Tier    │    │  - Qwen 2.5:7B    │
                   │  - Graph Engine     │    │    Class.    │    │  - Local inference │
                   │  - Vector Index     │    │    Cache     │    │  - OpenAI-compat   │
                   │                     │    │  - SLA       │    │    API             │
                   │  15 Doc Collections │    │    Timers    │    │                    │
                   │  9 Edge Collections │    │  - Rate      │    │  Port 11434        │
                   │  1 Named Graph      │    │    Limiting  │    │  (host machine)    │
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
| Domain Dashboard | `DomainDashboard.jsx` | Ticket queue grouped by IT domain, create ticket form, stats summary bar |
| Ticket Detail | `TicketDetail.jsx` | Full ticket view with status actions, resolve form, feedback widget, audit timeline |
| Resolve Form | `ResolveForm.jsx` | Resolution steps form with AI suggestion pre-fill and runbook selection |
| Feedback Widget | `FeedbackWidget.jsx` | Rate AI suggestion as helpful/not_helpful with optional comment |
| Analytics Dashboard | `AnalyticsDashboard.jsx` | Interactive charts (Recharts): category bar chart, status donut, priority breakdown, daily trend area chart, team workload, feedback stats, classifier agreement |
| Audit Timeline | `AuditTimeline.jsx` | Visual timeline of all actions on a ticket (classified, routed, picked up, resolved, feedback) |
| Stats Summary Bar | `StatsSummaryBar.jsx` | Animated counters showing total tickets, avg confidence, escalation rate, avg resolution time |
| Chat AI | `ChatPanel.jsx` | Zero-hallucination chat with Mindy AI, grounded in ArangoDB data |
| Status Bar | `StatusBar.jsx` | Real-time ArangoDB/Redis/Ollama health indicators |
| Enrichment Card | `EnrichmentCard.jsx` | Interactive Q&A for vague tickets with clickable suggestions |
| Screenshot Upload | `ScreenshotUpload.jsx` | Drag-drop image upload with OCR entity extraction |
| Override Modal | `OverrideModal.jsx` | Human override of AI classification with audit logging |
| Graph Visualization | `GraphVisualization.jsx` | Interactive force-directed knowledge graph |
| User Management | `UserManagement.jsx` | Admin panel for user CRUD and role assignment |
| Splash Screen | `DeskMindSplash.jsx` | Animated brand intro (3.2s) |

**Design**: Neural Dark + Light theme support — `#0C0C0F` dark / `#f5f5f4` light, `#F97316` orange accent, glass-morphism cards. 24 total components.

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
| `/api/tickets/{id}/feedback` | POST | Any authenticated | Rate AI suggestion (helpful/not_helpful) |
| `/api/tickets/{id}/override` | PUT | Engineer or Admin | Manual category override with correction tracking |
| `/api/tickets/{id}/enrich` | POST | Any authenticated | Re-classify with user-provided enrichment answers |
| `/api/tickets/{id}` | DELETE | Admin only | Delete a ticket |
| `/api/tickets/sla-breached` | GET | Engineer or Admin | List tickets that breached SLA deadline |
| `/api/stats` | GET | Any authenticated | Aggregated metrics (admin=global, engineer=team-scoped) |
| `/api/stats/tickets/{id}/timeline` | GET | Any authenticated | Audit trail for a ticket |
| `/api/incidents` | GET | Any authenticated | Proactive incident predictions (role-filtered) |
| `/api/corrections/stats` | GET | Admin | Correction analytics and classifier error rates |
| `/api/corrections/recompute-centroids` | POST | Admin | Recompute category centroids from corrected tickets |
| `/api/corrections/export` | GET | Admin | Export corrections as training data |
| `/api/upload` | POST | Any authenticated | Upload screenshot with OCR processing |
| `/api/chat` | POST | Any authenticated | Zero-hallucination chat grounded in ArangoDB data |
| `/api/graph` | GET | Any authenticated | Knowledge graph nodes and edges for visualization |
| `/health` | GET | Public | System health check + degradation level |

#### Classification Pipeline (5 Stages)

**Stage 1 — PREPARE** (4 services):
- **Text Preprocessor**: Cleans raw text before embedding — removes timestamps, replaces IP addresses with tokens, strips UUIDs and file paths, truncates to 2000 chars. Reduces noise from pasted logs/stack traces.
- **Entity Extractor**: Scans ticket text for known server names (15), service names (12), error patterns (20). Caches entity lists from ArangoDB with 5-min TTL.
- **Error Scanner**: Maps matched error codes to categories for confidence bonus. Service-to-category mapping (e.g., `postgresql` → Database).
- **Quality Scorer**: Multi-signal scorer combining 5 signals: infrastructure entities (+3), error codes (+3), description length (+1/+2), technical keywords (+1), title specificity (+1). Score >= 5 = HIGH, >= 3 = MEDIUM, else LOW. Caps confidence (HIGH=0.99, MEDIUM=0.85, LOW=0.75).

**Stage 2 — RETRIEVE** (4 parallel searches + re-ranking):
- **Vector Similarity**: Finds 5 most semantically similar past tickets using 384-dim MiniLM embeddings (title + description co-encoded) + ArangoDB vector index (cosine similarity).
- **Error Code Match**: Follows `triggered_by` edges from matched error codes to find past tickets with identical errors.
- **Graph Traversal**: Starting from mentioned server/service, follows `hosts` → `managed_by` → `affects` → `depends_on` → `member_of` edges to build infrastructure context.
- **Full-text Search**: Keyword index search on ticket descriptions for term-level matching.
- **Re-ranking**: Results re-ranked by combined score: 60% similarity + 20% recency + 20% effectiveness. Recent, proven resolutions surface above old/unverified ones.

**Stage 3 — CLASSIFY** (4 independent classifiers):

| Classifier | Weight | Method | Accuracy | Speed |
|-----------|--------|--------|----------|-------|
| LLM (Qwen 2.5:7B) | 0.40 | Reads ticket + all Stage 2 context with 12 disambiguation rules and 6 few-shot examples. Reasons about root cause. | **94.1%** | ~5-7s |
| Centroid Distance | 0.30 | Compares title+description embedding to 6 pre-computed category centroids | **73.5%** | ~5ms |
| KNN Voting | 0.15 | Top 5 similar tickets vote by category (weighted by similarity, confidence = weighted vote share) | **76.5%** | ~10ms |
| Keyword Rules | 0.15 | 25+ keywords per category with word-boundary matching (regex) | **67.7%** | ~1ms |

**Note**: All 4 classifiers run in parallel via `asyncio.gather()`. Total classification time = LLM time only (~2s), not the sum of all 4.

**Stage 4 — AGGREGATE** (Majority-Aware Voting Algorithm):
- 6-phase weighted voting protocol (hardened with ChatGPT review):
  - **Phase 0**: Single classifier (cap 0.50)
  - **Phase 1**: Unanimous agreement (cap 0.95)
  - **Phase 2**: Supermajority 3+ (strength check: avg conf >= 0.60)
  - **Phase 3**: Pair beats singles 2/1/1 (pair score >= best single - 0.05)
  - **Phase 4**: 2v2 split with known boundary overrides (e.g., Database vs Infrastructure → Centroid+KNN side preferred)
  - **Phase 5**: Total disagreement → weighted fallback (cap 0.50)
- Confidence formula: `0.60 × supporter_avg_conf + 0.25 × vote_share + 0.15 × weight_share`
- Error code confirmation bonus (+0.03), Graph context bonus (+0.02)
- Quality cap from Stage 1

**Stage 5 — DECIDE + ENRICH + GENERATE**:
- confidence >= 0.70 → Auto-route to team
- confidence < 0.70 → Escalate to human (`pending_human` status)
- Attach: suggested resolution, recommended expert, matching runbook
- **AI Resolution Generator**: If no good historical resolution exists (effectiveness < 0.50), the LLM generates a custom step-by-step fix grounded in similar past resolutions + graph context + error patterns
- **Enrichment Agent**: For vague tickets (LOW quality), generates personalized follow-up questions with clickable suggestions from user's ticket history
- **SLA Timer**: Redis TTL key per ticket (Critical=2h, High=4h, Medium=8h, Low=24h)

#### Resolution Pipeline (Retrieval + AI Generation)
- **Historical retrieval**: Finds best resolution from 3 sources: similar tickets, error-matched tickets, graph context (past tickets on same server). Ranks by effectiveness score (0.0-1.0).
- **AI Resolution Generator** (NEW): When no good historical resolution exists (effectiveness < 0.50), the LLM generates a custom step-by-step fix using:
  - Reference solutions from similar past tickets (with effectiveness scores)
  - Infrastructure context from the knowledge graph (server type, hosted services, team experts)
  - Error code patterns and their known fixes
  - Quality gate: only generates when reference context exists (no hallucination from nothing)
  - Output: 3-7 actionable steps + reasoning + confidence + sources used
- Matches runbooks by category
- Identifies expert from graph traversal (team member with relevant expertise)
- Stores `suggested_resolution`, `resolution_effectiveness`, `ai_generated_resolution`, `suggested_runbook`, and `recommended_expert` directly in the ticket document

#### Ticket Ownership
- When an engineer picks up a ticket (status -> `in_progress`), the `picked_up_by` field is set to the engineer's email
- If another engineer tries to pick up the same ticket, the API returns a 409 Conflict
- Only the engineer who picked up the ticket (or an admin) can resolve it
- When a ticket is escalated or re-routed, `picked_up_by` is cleared

#### Effectiveness Feedback Loop
- Users can rate the AI suggestion via `POST /api/tickets/{id}/feedback` (helpful/not_helpful)
- When an engineer resolves a ticket, they indicate whether the AI suggestion was used ("yes", "partially", "no")
- Resolved tickets (status `resolved`) are included in the vector similarity search alongside closed tickets, so user-resolved incidents feed back into future resolution suggestions
- This creates a live feedback loop: more resolved tickets with confirmed AI suggestions improve the quality of future suggestions

#### Graceful Degradation

| Level | Condition | Available Classifiers | Weights | Expected Accuracy |
|-------|-----------|----------------------|---------|-------------------|
| 4 (Full) | All systems up | LLM + KNN + Centroid + Keywords | 0.40, 0.15, 0.30, 0.15 | **94.1%** (benchmark-verified) |
| 3 (No Data) | Ollama up, DB empty | LLM + Keywords | 0.80, 0.20 | ~80% |
| 2 (No LLM) | Ollama down, DB up | KNN + Centroid + Keywords | 0.25, 0.50, 0.25 | ~70% |
| 1 (Emergency) | Ollama down, DB empty | Keywords only | 1.00 | ~55% |

Health checks run every 5 seconds (cached). The system never fully crashes — it always falls back to keyword classification.

#### Evaluated Accuracy (35-ticket fixed benchmark)

Measured on a hand-labeled test set of 35 tickets covering all 6 categories + boundary/edge cases:

| Category | Accuracy | Avg Confidence |
|----------|----------|----------------|
| Infrastructure | **100%** (5/5) | 0.848 |
| Network | **100%** (6/6) | 0.738 |
| Security | **100%** (5/5) | 0.770 |
| Access Management | **100%** (5/5) | 0.854 |
| Application | **85.7%** (6/7) | 0.833 |
| Database | **83.3%** (5/6) | 0.833 |
| **Overall** | **94.1%** (32/34) | **0.812** |

**By difficulty level:**
| Difficulty | Accuracy |
|------------|----------|
| Clear (25 tickets) | **100%** |
| Boundary (5 tickets) | **80%** |
| Edge: multi-domain (2 tickets) | **100%** |

**Improvement journey** (each step measured independently):
| Step | Accuracy | Delta |
|------|----------|-------|
| Baseline (R2) | 85.3% | — |
| + Title+description embedding | 94.1% | **+8.8%** |
| + KNN confidence fix | 94.1% | +0.0% |
| + Text preprocessing | 94.1% | +0.0% |
| + Retrieval re-ranking | 94.1% | +0.0% |
| + Quality scorer upgrade | **94.1%** | +0.0% |

The ensemble (94.1%) outperforms every individual classifier, proving the value of multi-model voting.

### 3.3 Knowledge Graph — ArangoDB 3.12

ArangoDB serves as a **triple-purpose database**:
1. **Document Store** — tickets, teams, engineers, servers, services, resolutions, runbooks
2. **Graph Engine** — infrastructure relationships via 9 edge collections
3. **Vector Database** — 384-dim embeddings with APPROX_NEAR_COSINE similarity search

**15 Document Collections**: tickets, teams, engineers, servers, services, network_devices, error_codes, runbooks, resolutions, routing_rules, audit_log, category_centroids, users, corrections, repeated_issues

**9 Edge Collections**: hosts, managed_by, depends_on, member_of, affects, assigned_to, resolved_with, references, triggered_by

**1 Named Graph**: `deskmind_graph` — connects all collections into a traversable knowledge graph

**Key Indexes**:
- Vector index on `tickets.embedding` (384 dimensions, cosine metric)
- Fulltext index on `tickets.description`
- Persistent indexes on frequently queried fields

### 3.4 Caching & Performance — Redis 7

**Two-Tier Classification Cache:**
- **Tier A** (Exact Match): SHA-256 hash of title+description → cached result, 1h TTL, <5ms latency
- **Tier B** (Semantic Match): Cosine similarity > 0.95 against last 100 embeddings → cached result, <10ms latency
- **Cache invalidation**: Both tiers flushed when a human correction is recorded (prevents stale results)

**Other caches:**
- Health check results: 5-second TTL
- Entity lists (servers, services, error codes): 5-minute TTL
- Category centroids: 1-hour in-memory cache
- Incident predictions: 60-second TTL per user role+team

**Rate Limiting:** Redis sliding-window — 50 req/min per user, 200 req/min global

**Circuit Breaker:** Ollama fast-fail after 3 consecutive failures, 30s recovery test (CLOSED → OPEN → HALF_OPEN)

### 3.5 LLM — Qwen 2.5:7B via Ollama

- **Model**: Qwen 2.5:7B (7 billion parameters, upgraded from 3B for better reasoning)
- **Runtime**: Ollama (local inference, no cloud API calls)
- **API**: OpenAI-compatible chat completions endpoint
- **Purpose**: Primary classifier + AI resolution generator + chat interface
- **Prompt engineering**: Root-cause classification instruction with 12 disambiguation rules, 6 few-shot examples, and context injection from Stage 2
- **Temperature**: 0.1 for classification (deterministic), 0.2 for resolution generation (slightly creative)

---

## 4. Technology Stack

### Core Technologies

| Technology | Version | Role | Why We Chose It |
|-----------|---------|------|-----------------|
| **ArangoDB** | 3.12 CE | Knowledge Graph + Vector DB + Document Store | Only DB that natively combines graph, document, and vector search in one engine. Eliminates need for separate Neo4j + Pinecone + MongoDB. |
| **Qwen 2.5:7B** | 7B | Primary LLM Classifier + Resolution Generator | Upgraded from 3B for better root-cause reasoning. Runs on CPU without GPU. |
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
| `bcrypt` | Password hashing for secure credential storage |
| `pytesseract` | OCR text extraction from screenshots |
| `python-multipart` | Multipart form data parsing for file uploads |
| `python-dotenv` | Environment variable loading |

### Frontend Libraries

| Library | Purpose |
|---------|---------|
| `react` + `react-dom` | UI framework (v19.1) |
| `vite` | Build tooling + dev server with API proxy (v6.3) |
| `recharts` | Interactive charts for analytics dashboard |
| `react-force-graph-2d` | Force-directed knowledge graph visualization |
| `socket.io-client` | Real-time ticket updates via WebSocket |

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
│  Model: qwen2.5:7b         │
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
| Total documents | 1,702 |
| Total edges | 3,492 |
| Tickets (seed + synthetic) | 855 |
| Resolutions | 736 |
| Category centroids | 6 |
| Teams | 6 |
| Engineers | 12 |
| Servers | 15 |
| Services | 12 |
| Error codes | 20 |
| Runbooks | 10 |
| Routing rules | 24 |
| Evaluation test set | 35 (hand-labeled, fixed benchmark) |

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
| **User** | All domains | Yes | No | No | No | No |

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
- **Rate limiting**: Redis sliding-window — 50 req/min per user, 200 req/min global (POST /api/tickets only).
- **Circuit breaker**: Ollama fast-fail after 3 consecutive failures, prevents cascading failures.
- **SLA management**: Redis TTL-based timers per ticket priority (Critical=2h to Low=24h).

---

## 9. Key Differentiators

| Feature | DeskMind | Typical AI Classifier |
|---------|----------|----------------------|
| Classification method | 4-classifier ensemble with 6-phase majority-aware voting (**94.1% accuracy**) | Single LLM call (~80%) |
| Context retrieval | GraphRAG (vector + graph + error + fulltext) with re-ranking | Simple RAG (vector only) |
| Infrastructure awareness | Knowledge graph with server → service → team → engineer relationships | None |
| Resolution | **AI generates custom fixes** grounded in past resolutions + graph context | None or basic retrieval |
| Failure handling | 4-level graceful degradation with circuit breaker | Single point of failure |
| Self-learning | 3 feedback loops: corrections → centroid retraining, resolution feedback, repeated issue detection | Static model |
| Proactive intelligence | Incident prediction (cluster + trend + spike detection) | Reactive only |
| Vague ticket handling | Enrichment agent generates personalized follow-up questions | Reject or generic response |
| Screenshot understanding | OCR + screenshot type detection + entity extraction from images | Text-only |
| Confidence calibration | 6-phase voting + quality cap + contextual bonuses + boundary overrides | Raw LLM logprobs |
| Data privacy | Fully local inference (Ollama + Qwen 2.5:7B, no cloud API) | Cloud API dependency |
| Explainability | Full audit trail with 4 classifier votes + reasoning + confidence breakdown | Black box |

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
| **Access Management** | LDAP sync failure, SSO login broken, MFA enrollment issues | Access Management |

Each category has **4 routing rules** (critical/high/medium/low priority), totaling 24 rules that map `{category, priority}` → team.
