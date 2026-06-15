# DeskMind — AI-Powered IT Ticket Routing

> Classify, route, and **resolve** IT support tickets automatically using a 4-classifier ensemble, knowledge graph, and local LLM — all on-premise, zero cloud APIs. **94.1% accuracy**, benchmark-verified.

---

## Key Features

- **4-Classifier Ensemble** — LLM (40%), Centroid (30%), KNN (15%), Keyword (15%) with 6-phase majority-aware voting. **94.1% accuracy** on 35-ticket benchmark.
- **AI Resolution Generator** — LLM generates custom step-by-step fixes grounded in past resolutions + knowledge graph context (hallucination-resistant: a quality gate returns nothing when no reference data exists).
- **Knowledge Graph** — ArangoDB graph with teams, engineers, servers, services, error codes powering context-aware routing
- **Enrichment Agent** — Detects vague tickets, generates personalized follow-up questions from user history
- **Incident Prediction** — Proactive detection of clusters (3+ same team/4h), trends (50%+ spike), and volume spikes (5+/hour)
- **Self-Learning** — 3 feedback loops: human corrections retrain centroids, resolution quality tracking, repeated issue detection
- **Hallucination-resistant Chat** — Mindy AI uses rule-based intent parsing + real DB queries; the LLM only formats responses, it never invents data
- **OCR Screenshot Analysis** — Tesseract OCR extracts text from uploaded screenshots, classifies screenshot type, feeds to classifiers
- **On-Premise** — Ollama (Qwen 2.5:7B), MiniLM embeddings, no cloud APIs; your data stays with you
- **Graceful Degradation** — 4 levels of fallback with circuit breaker; system never fully crashes
- **Explainable AI** — Every classification shows individual classifier votes, confidence scores, and reasoning

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19 + Vite 6 | Dashboard, analytics, knowledge graph viz, 24 components |
| **Backend** | FastAPI (Python 3.12) | REST API (32 endpoints), classification pipeline, Socket.IO |
| **LLM** | Ollama + Qwen 2.5:7B | Local LLM inference for classification + resolution generation |
| **Embeddings** | all-MiniLM-L6-v2 | 384-dim sentence embeddings (title + description co-encoded) |
| **Graph DB** | ArangoDB 3.12 | Knowledge graph + vector search + document store (3-in-1) |
| **Cache** | Redis 7 | Two-tier classification cache, SLA timers, rate limiting |
| **NLP** | spaCy (en_core_web_sm) | Entity extraction from ticket text |
| **OCR** | Tesseract + pytesseract | Screenshot text extraction with type detection |
| **Real-time** | Socket.IO | Live ticket updates, toast notifications |

---

## Architecture

```
                         +------------------+
                         |   React Frontend |
                         |   (port 3000)    |
                         +--------+---------+
                                  |
                           REST + Socket.IO
                                  |
                         +--------v---------+
                         |  FastAPI Backend  |
                         |   (port 8000)    |
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
     +--------v-------+  +-------v--------+  +-------v--------+
     |   ArangoDB      |  |    Redis       |  |    Ollama      |
     | Knowledge Graph |  | 2-Tier Cache   |  | Local LLM      |
     | Vector Search   |  | SLA Timers     |  | Qwen 2.5:7B    |
     |  (port 8530)    |  |  (port 6379)   |  | (port 11434)   |
     +-----------------+  +----------------+  +----------------+
```

**5-Stage Classification Pipeline:**

```
Ticket → Preprocess → Entity Extract → Embed (MiniLM) → 4 Classifiers (parallel)
                                                              |
                                              LLM ──────┐    |
                                              Centroid ──┤ Majority-Aware → Route/Escalate
                                              KNN ───────┤   Voting          + Generate
                                              Keyword ───┘   (6 phases)      Resolution
```

---

## Classification Accuracy

**94.1%** on a fixed 35-ticket benchmark (up from 85.3% baseline):

| Category | Accuracy | Avg Confidence |
|----------|----------|----------------|
| Infrastructure | 100% | 0.848 |
| Network | 100% | 0.738 |
| Security | 100% | 0.770 |
| Access Management | 100% | 0.854 |
| Application | 85.7% | 0.833 |
| Database | 83.3% | 0.833 |

**Individual Classifier vs Ensemble:**

| Classifier | Alone | In Ensemble |
|-----------|-------|-------------|
| LLM (Qwen 2.5:7B) | 94.1% | **94.1%** (same accuracy, but with fallback) |
| Centroid | 73.5% | -- |
| KNN | 76.5% | -- |
| Keyword | 67.7% | -- |

The ensemble matches the best classifier but adds **resilience** — if Ollama crashes, the remaining 3 classifiers are projected to still achieve ~70% (estimate; not separately benchmarked).

---

## Quick Start (< 5 minutes)

### Prerequisites

- **Docker Desktop** ([download](https://www.docker.com/products/docker-desktop/))
- **Ollama** ([download](https://ollama.com/download)) — for LLM classification

### 1. Clone and configure

```bash
git clone https://github.com/arif-asadullah/AI-Ticket-Routing.git
cd AI-Ticket-Routing
cp .env.example .env
```

### 2. Start Ollama (host machine)

```bash
ollama serve              # start the server
ollama pull qwen2.5:7b    # download the model (~4.7 GB)
```

### 3. Start all services

```bash
docker compose up --build -d
```

First run downloads ~3 GB of images. Wait until all 4 services show **(healthy)**:

```bash
docker compose ps
```

### 4. Seed the database

```bash
docker compose exec backend python scripts/seed_db.py
```

### 5. Open the app

| Service | URL |
|---------|-----|
| DeskMind UI | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| ArangoDB Admin | http://localhost:8530 |

**Login:** `arif.asadullah@schwettmann.in` / `DeskMind@2026`

---

## API Endpoints (32)

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/bootstrap` | Create first admin account |
| `POST` | `/api/auth/login` | Login, returns JWT tokens |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `GET` | `/api/auth/me` | Get current user |
| `POST` | `/api/auth/register` | Register new user (admin only) |
| `GET` | `/api/auth/users` | List all users (admin only) |
| `PATCH` | `/api/auth/users/{email}/toggle-active` | Enable/disable user |
| `GET` | `/api/auth/engineers` | List engineers |

### Tickets
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tickets` | List tickets (filtered by team for engineers) |
| `POST` | `/api/tickets` | Create + classify + route (+ AI resolution) |
| `GET` | `/api/tickets/sla-breached` | Tickets past SLA deadline |
| `GET` | `/api/tickets/{id}` | Get ticket details |
| `PATCH` | `/api/tickets/{id}/status` | Update status (pick up, escalate) |
| `PUT` | `/api/tickets/{id}/override` | Override AI classification with correction tracking |
| `POST` | `/api/tickets/{id}/enrich` | Re-classify with enrichment answers |
| `POST` | `/api/tickets/{id}/resolve` | Resolve with steps + effectiveness tracking |
| `POST` | `/api/tickets/{id}/feedback` | Rate resolution (helpful/not_helpful) |
| `DELETE` | `/api/tickets/{id}` | Delete ticket (admin only) |

### Intelligence & Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health + degradation level |
| `POST` | `/api/chat` | Mindy AI chat (grounded, hallucination-resistant) |
| `GET` | `/api/stats` | Dashboard statistics (team-scoped for engineers) |
| `GET` | `/api/stats/tickets/{id}/timeline` | Ticket audit timeline |
| `GET` | `/api/graph` | Knowledge graph nodes and edges |
| `GET` | `/api/incidents` | Proactive incident predictions (role-filtered) |
| `POST` | `/api/upload` | Upload screenshot with OCR processing |
| `GET` | `/api/upload/{file_id}` | Retrieve uploaded file metadata |
| `GET` | `/api/runbooks/{runbook_id}` | Get runbook by ID |
| `GET` | `/api/corrections/stats` | Correction analytics |
| `POST` | `/api/corrections/recompute-centroids` | Retrain centroids from corrections |
| `GET` | `/api/corrections/repeated-issues` | List detected recurring issue clusters |
| `POST` | `/api/corrections/detect-repeated-issues` | Trigger repeated-issue detection |
| `GET` | `/api/corrections/export` | Export corrections dataset |

Interactive docs: http://localhost:8000/docs

---

## Classification System

### 4-Classifier Ensemble

| Classifier | Weight | Method | Accuracy |
|-----------|--------|--------|----------|
| **LLM** | 0.40 | Qwen 2.5:7B via Ollama — root-cause analysis with 12 disambiguation rules | 94.1% |
| **Centroid** | 0.30 | Cosine distance to category centroid embeddings (MiniLM) | 73.5% |
| **KNN** | 0.15 | K-nearest neighbors from similar resolved tickets (weighted vote share) | 76.5% |
| **Keyword** | 0.15 | Pattern matching against 100+ domain-specific terms | 67.7% |

### 6 IT Domains

Infrastructure, Application, Database, Network, Security, Access Management

### Majority-Aware Voting (6 phases)

| Phase | Condition | Logic |
|-------|-----------|-------|
| 0 | Single classifier | Take it (cap 0.50) |
| 1 | Unanimous | All agree (cap 0.95) |
| 2 | Supermajority (3+) | Strength check: avg conf >= 0.60 |
| 3 | Pair vs singles (2/1/1) | Pair score >= best single - 0.05 |
| 4 | 2v2 split | Boundary overrides (e.g., Database vs Infra) + 4-step tiebreaker |
| 5 | Total disagreement | Weighted fallback (cap 0.50) |

### Graceful Degradation

| Level | Condition | Classifiers Active | Accuracy |
|-------|-----------|-------------------|----------|
| 4 (Full) | All systems up | LLM + Centroid + KNN + Keyword | **94.1%** |
| 3 (No Data) | DB empty | LLM + Keyword | ~80% (projected) |
| 2 (No LLM) | Ollama down | Centroid + KNN + Keyword | ~70% (projected) |
| 1 (Emergency) | Both down | Keyword only | ~68% (keyword-only, measured) |

---

## AI Features

| Feature | Description |
|---------|-------------|
| **AI Resolution Generator** | LLM generates custom fix steps grounded in past resolutions + graph context. Quality gate: only generates when reference data exists (hallucination-resistant). |
| **Enrichment Agent** | Generates personalized follow-up questions for vague tickets using user history + knowledge graph |
| **Incident Prediction** | Cluster (3+ same team/4h), Trend (50%+ week-over-week), Spike (5+/hour). Role-filtered. |
| **Self-Learning** | 3 loops: correction → centroid retrain, resolution feedback → effectiveness, repeated issue detection |
| **OCR Screenshot Analysis** | Tesseract + screenshot type detection (stack trace, HTTP error, log, terminal, dashboard) |
| **Two-Tier Cache** | Tier A: SHA-256 exact match (<5ms). Tier B: semantic similarity >0.95 (<10ms). Invalidated on corrections. |
| **Circuit Breaker** | Ollama fast-fail after 3 failures, 30s recovery test (CLOSED → OPEN → HALF_OPEN) |
| **SLA Timers** | Redis TTL keys — Critical=2h, High=4h, Medium=8h, Low=24h. Breach detection. |
| **Rate Limiting** | 50/user/min, 200/global/min, Redis sliding window |
| **Hallucination-resistant Chat** | Mindy: rule-based intent → ArangoDB query → LLM formats response |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API server |
| `OLLAMA_MODEL` | `qwen2.5:7b` | LLM model tag |
| `ARANGO_URL` | `http://localhost:8530` | ArangoDB endpoint |
| `ARANGO_DB` | `ticket_agent` | Database name |
| `ARANGO_USER` | `root` | Database user |
| `ARANGO_PASSWORD` | *(empty)* | Database password |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence embedding model |
| `CONFIDENCE_THRESHOLD` | `0.70` | Auto-route confidence threshold |

---

## Repository Structure

```
backend/
  app/main.py              FastAPI entry point + middleware + Socket.IO
  api/                     REST endpoints (auth, tickets, chat, stats, graph, health,
                           incidents, corrections, upload)
  core/auth.py             JWT auth, password hashing, RBAC (admin, engineer, user)
  core/config.py           Pydantic settings (reads .env)
  middleware/rate_limit.py  Redis sliding-window rate limiter
  schemas/ticket.py        Request/response Pydantic models
  services/
    orchestrator.py        5-stage classification pipeline + text preprocessing
    aggregator.py          6-phase majority-aware voting + confidence calibration
    llm_classifier.py      Qwen 2.5:7B via Ollama (weight: 0.40)
    centroid_classifier.py Embedding centroid distance (weight: 0.30)
    knn_classifier.py      K-nearest neighbor weighted voting (weight: 0.15)
    keyword_classifier.py  Pattern matching (weight: 0.15)
    resolution_generator.py AI resolution generation (grounded, hallucination-resistant)
    enrichment_agent.py    Follow-up questions for vague tickets
    cache.py               Two-tier Redis cache (text hash + semantic)
    corrections.py         Human override tracking + centroid retraining
    repeated_issues.py     Cluster detection for recurring problems
    router.py              SLA timers + team routing
    circuit_breaker.py     Ollama circuit breaker (3-state)
    ocr_engine.py          Screenshot OCR + type detection
    quality_scorer.py      Multi-signal ticket quality assessment
    retrieval.py           Hybrid retrieval (vector + error + graph + fulltext)
    entity_extractor.py    Server, service, error code extraction
    chat_intent.py         Rule-based intent parser for Mindy
    chat_data.py           ArangoDB query builder for Mindy
    socketio_manager.py    Real-time event broadcasting
    database.py            ArangoDB connection

frontend/
  src/App.jsx              Main layout, auth, degraded mode banner
  src/components/          24 components (dashboard, tickets, analytics, graph, chat,
                           enrichment, override, resolve, OCR upload, user management)
  src/services/api.js      Authenticated API client with token refresh
  src/services/socket.js   Socket.IO real-time hook
  src/theme/ThemeContext.jsx  Light/dark theme system

data/
  seed/seed_data.yaml      6 teams, 12 engineers, 55 tickets, routing rules
  synthetic/               800 AI-generated tickets (Claude + GPT-4o + Phi-4 + noise)
  eval/                    35-ticket benchmark + evaluation results

scripts/
  seed_db.py               Database seeder with embeddings + centroids
  evaluate.py              Classification benchmark (--tag, --compare)

docs/
  nasscom-r2/              Hackathon Final Round documents (8 deliverables)
  architecture/            Classification pipeline, graph traversal, classifiers docs
  schema/                  ArangoDB collections, edges, indexes
  classification-improvements.md  85.3% → 94.1% accuracy improvement story

docker-compose.yml         4 services: ArangoDB, Redis, Backend, Frontend
```

---

## Data

| Metric | Count |
|--------|-------|
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
| Graph edges | ~3,500 (generated at seed time) |
| Evaluation benchmark | 35 hand-labeled tickets |

---

## Team

| Name | Role | Responsibilities |
|------|------|-----------------|
| **Arif Asadullah** | Tech Lead | Architecture, backend, AI pipeline, deployment, docs |
| **Mohit Tomar** | Backend Developer | Redis cache, SLA, rate limiting, routing |
| **Aakarsh** | ML Engineer | Classifiers, evaluation, data generation |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `docker: command not found` | Install Docker Desktop and make sure it's running |
| `port already in use` | Stop other services on ports 3000, 8000, 6379, 8530 |
| Backend health shows arango `"unavailable"` | Run `docker compose restart backend` |
| Login fails intermittently | Rebuild backend: `docker compose up -d --build backend` |
| Frontend shows "Could not load tickets" | Wait 10s for backend to start, then refresh |
| Ollama not reachable | Ensure `ollama serve` is running on host machine |
| Classification takes >30s | Normal for first request (model loading). Subsequent: ~5-7s. Cached: <5ms |

---

## Documentation

- **[Solution Architecture](docs/nasscom-r2/01-solution-architecture.md)** — System design, components, pipeline
- **[Low Level Design](docs/nasscom-r2/02-low-level-design.md)** — Module specs, algorithms, data structures
- **[Classification Improvements](docs/classification-improvements.md)** — 85.3% → 94.1% accuracy story
- **[Majority-Aware Voting](docs/majority-aware-voting.md)** — 6-phase voting algorithm
- **[Self-Learning](docs/self-learning.md)** — 3 feedback loops
- **[Incident Prediction](docs/incident-prediction.md)** — Proactive pattern detection
- **[OCR Screenshot Analysis](docs/ocr-screenshot-analysis.md)** — Image processing pipeline
- **[Deployment Guide](docs/deployment.md)** — Step-by-step setup

---

Built for the **Nasscom AI-Code-Sarathi Excel Hackathon — Final Round (Jury)**
