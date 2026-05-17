# DeskMind — AI-Powered IT Ticket Routing

> Classify, route, and resolve IT support tickets automatically using a 4-classifier ensemble, knowledge graph, and local LLM — all on-premise, zero cloud APIs.

---

## Key Features

- **4-Classifier Ensemble** — LLM (40%), Centroid (30%), KNN (15%), Keyword (15%) vote together for high accuracy
- **Knowledge Graph** — ArangoDB graph with teams, engineers, servers, services, error codes powering context-aware routing
- **Zero Hallucination Chat** — Mindy AI assistant uses rule-based intent parsing + real DB queries; LLM only formats responses
- **On-Premise** — Ollama (Qwen 2.5:3B), MiniLM embeddings, no cloud APIs; your data stays with you
- **Graceful Degradation** — 4 levels of fallback; system never fully breaks even if LLM goes down
- **Explainable AI** — Every classification shows individual classifier votes, confidence scores, and reasoning

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19 + Vite 6 | Dashboard, analytics, knowledge graph viz |
| **Backend** | FastAPI (Python 3.12) | REST API, classification pipeline, Socket.IO |
| **LLM** | Ollama + Qwen 2.5:3B | Local LLM inference for classification |
| **Embeddings** | all-MiniLM-L6-v2 | 384-dim sentence embeddings for semantic search |
| **Graph DB** | ArangoDB 3.12 | Knowledge graph, vector search, document store |
| **Cache** | Redis 7 | Two-tier cache, SLA timers, rate limiting, pub-sub |
| **NLP** | spaCy (en_core_web_sm) | Entity extraction from ticket text |
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
     | Knowledge Graph |  | Cache + SLA    |  | Local LLM      |
     | Vector Search   |  | Rate Limiting  |  | Qwen 2.5:3B    |
     |  (port 8530)    |  |  (port 6379)   |  | (port 11434)   |
     +-----------------+  +----------------+  +----------------+
```

**Classification Pipeline:**

```
Ticket → PII Mask → Entity Extract → Embed (MiniLM) → 4 Classifiers (parallel)
                                                            |
                                            LLM ──────┐    |
                                            Centroid ──┤ Weighted Vote → Route/Escalate
                                            KNN ───────┤
                                            Keyword ───┘
```

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
ollama serve          # start the server
ollama pull qwen2.5:3b  # download the model (~1.9 GB)
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

### 6. Submit your first ticket

Create a ticket from the UI or via curl:

```bash
curl -X POST http://localhost:8000/api/tickets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Server down","description":"prod-app-01 is unresponsive since 6 AM","priority":"critical"}'
```

---

## API Endpoints

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
| `POST` | `/api/tickets` | Create + classify + route a ticket |
| `GET` | `/api/tickets/sla-breached` | Tickets past SLA deadline |
| `GET` | `/api/tickets/{id}` | Get ticket details |
| `PATCH` | `/api/tickets/{id}/status` | Update status (pick up, escalate) |
| `PUT` | `/api/tickets/{id}/override` | Override AI classification |
| `POST` | `/api/tickets/{id}/resolve` | Resolve with steps |
| `POST` | `/api/tickets/{id}/feedback` | Rate classification quality |
| `DELETE` | `/api/tickets/{id}` | Delete ticket |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health + degradation level |
| `POST` | `/api/chat` | Mindy AI chat (zero hallucination) |
| `GET` | `/api/stats` | Dashboard statistics |
| `GET` | `/api/stats/tickets/{id}/timeline` | Ticket audit timeline |
| `GET` | `/api/graph` | Knowledge graph data |

Interactive docs: http://localhost:8000/docs

---

## Classification System

### 4-Classifier Ensemble

| Classifier | Weight | Method |
|-----------|--------|--------|
| **LLM** | 0.40 | Qwen 2.5:3B via Ollama — root-cause analysis with few-shot prompting |
| **Centroid** | 0.30 | Cosine distance to category centroid embeddings (MiniLM) |
| **KNN** | 0.15 | K-nearest neighbors from similar resolved tickets |
| **Keyword** | 0.15 | Pattern matching against domain-specific terms |

### 6 IT Domains

Infrastructure, Application, Database, Network, Security, Access Management

### Confidence & Routing

- **>= 70%** confidence → auto-routed to team
- **< 70%** confidence → escalated for human review
- **< 50%** (emergency mode) → pending_human queue

### Graceful Degradation

| Level | Condition | Classifiers Active |
|-------|-----------|-------------------|
| 4 (Full) | All systems up | LLM + Centroid + KNN + Keyword |
| 3 (No Data) | DB empty | LLM + Keyword |
| 2 (No LLM) | Ollama down | Centroid + KNN + Keyword |
| 1 (Emergency) | Both down | Keyword only |

---

## Key Backend Services

| Service | File | Description |
|---------|------|-------------|
| Two-tier cache | `backend/services/cache.py` | Tier A: exact text hash (<5ms), Tier B: semantic similarity >0.95 (<150ms) |
| SLA timers | `backend/services/router.py` | Redis TTL keys — Critical=2h, High=4h, Medium=8h, Low=24h |
| Circuit breaker | `backend/services/circuit_breaker.py` | Ollama fast-fail after 3 failures, 30s recovery test |
| Rate limiting | `backend/middleware/rate_limit.py` | 50/user/min, 200/global/min, Redis sliding window |
| Classification | `backend/services/orchestrator.py` | 5-stage pipeline with parallel classifier execution |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API server |
| `OLLAMA_MODEL` | `qwen2.5:3b` | LLM model tag |
| `ARANGO_URL` | `http://localhost:8530` | ArangoDB endpoint |
| `ARANGO_DB` | `ticket_agent` | Database name |
| `ARANGO_USER` | `root` | Database user |
| `ARANGO_PASSWORD` | *(empty)* | Database password |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence embedding model |
| `CONFIDENCE_THRESHOLD` | `0.70` | Auto-route confidence threshold |
| `LOG_LEVEL` | `INFO` | Log level |

---

## Repository Structure

```
backend/
  app/main.py              FastAPI entry point + middleware + Socket.IO
  api/                     REST endpoints (auth, tickets, chat, stats, graph, health)
  core/auth.py             JWT auth, password hashing, RBAC
  core/config.py           Pydantic settings (reads .env)
  middleware/rate_limit.py  Redis sliding-window rate limiter
  schemas/ticket.py        Request/response Pydantic models
  services/
    orchestrator.py        5-stage classification pipeline
    aggregator.py          Weighted voting + confidence calibration
    llm_classifier.py      Qwen 2.5:3B via Ollama
    centroid_classifier.py Embedding centroid distance
    knn_classifier.py      K-nearest neighbor voting
    keyword_classifier.py  Pattern matching
    cache.py               Two-tier Redis cache (text hash + semantic)
    router.py              SLA timers + team routing
    circuit_breaker.py     Ollama circuit breaker (3-state)
    chat_engine.py         Mindy AI — zero hallucination chat
    socketio_manager.py    Real-time event broadcasting
    database.py            ArangoDB connection
  Dockerfile               Python 3.12-slim, multi-stage

frontend/
  src/App.jsx              Main layout, auth, degraded mode banner
  src/components/
    DomainDashboard.jsx    6-domain card view with filters
    TicketDetail.jsx       Ticket detail + classifier votes + override
    OverrideModal.jsx      Analyst override classification modal
    AnalyticsDashboard.jsx Charts: category, status, confidence, trends
    GraphVisualization.jsx Force-directed knowledge graph
    ChatPanel.jsx          Mindy AI floating chat
    UserManagement.jsx     Admin user CRUD
  src/services/api.js      Authenticated API client with token refresh
  src/services/socket.js   Socket.IO real-time hook
  src/theme/ThemeContext.jsx  Light/dark theme system
  Dockerfile               Node 20, Vite build

data/
  seed/seed_data.yaml      6 teams, 12 engineers, 55 tickets, routing rules
  synthetic/               800 AI-generated tickets for training

docs/
  architecture/            Classification pipeline, graph traversal docs
  nasscom-r2/              Hackathon submission documents
  schema/                  ArangoDB collections, edges, indexes

scripts/
  seed_db.py               Database seeder with embeddings
  generate_*.py            Synthetic ticket generators

docker-compose.yml         4 services: ArangoDB, Redis, Backend, Frontend
```

---

## Team

| Name | Role | Responsibilities |
|------|------|-----------------|
| **Arif Asadullah** | Tech Lead | Architecture, backend, deployment, docs |
| **Mohit Tomar** | Backend Developer | Redis cache, SLA, rate limiting, routing |
| **Subasri Chandrasekaran** | Frontend Developer | Dashboard, graph viz, override UI |
| **Aakarsh** | ML Engineer | Classifiers, evaluation, data generation |
| **Anil Kumar Choudhury** | QA Engineer | Test suites, dataset validation |

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
| Classification takes >30s | Normal for first request (model loading). Subsequent: ~10-15s. Cached: <5ms |

---

## Links

- **Jira:** [ATR project on nasscomrag.atlassian.net](https://nasscomrag.atlassian.net)
- **Docs:** [docs/](docs/)
- **API Docs:** http://localhost:8000/docs (when running)

---

Built for the **Nasscom Agentic AI Hackathon — Round 2**
