# AI-Ticket-Routing

AI-powered ticket routing system using RAG over a knowledge graph, with local LLM inference.

**Stack:** FastAPI + React + ArangoDB + Redis + Ollama (Qwen 2.5:3B)

---

## Setup and Run (step by step)

> Follow these steps in order. Each step has the exact command and expected result.

### Step 1: Prerequisites

Install **Docker Desktop** (required):

- **macOS:** Download from https://www.docker.com/products/docker-desktop/ (choose Apple Silicon or Intel). Open the `.dmg`, drag to Applications, launch Docker Desktop, and wait for it to say "Running".
- **Windows:** Download from https://www.docker.com/products/docker-desktop/. Run the installer, enable WSL 2 when prompted, restart if asked, and launch Docker Desktop.

Verify Docker is working:

```bash
docker --version
```

Expected output (version may differ):

```
Docker version 28.x.x, build xxxxxxx
```

### Step 2: Clone the repository

```bash
git clone git@github.com:arif-asadullah/AI-Ticket-Routing.git
cd AI-Ticket-Routing
```

If SSH fails, use HTTPS instead:

```bash
git clone https://github.com/arif-asadullah/AI-Ticket-Routing.git
cd AI-Ticket-Routing
```

### Step 3: Create environment file

```bash
cp .env.example .env
```

No edits needed — defaults work for local development.

### Step 4: Start all services

```bash
docker compose up --build
```

First run downloads ~3 GB of images and dependencies. Takes 5-10 minutes depending on internet speed. Subsequent runs take seconds.

Wait until you see logs from all 4 services (arangodb, redis, backend, frontend). The backend will print:

```
backend-1  | INFO:     Application startup complete.
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

To run in background (detached) instead:

```bash
docker compose up --build -d
```

### Step 5: Verify all services are healthy

```bash
docker compose ps
```

Expected output — all 4 should show **(healthy)**:

```
NAME                 IMAGE              SERVICE    STATUS
project-arangodb-1   arangodb:3.12      arangodb   Up (healthy)
project-redis-1      redis:7            redis      Up (healthy)
project-backend-1    project-backend    backend    Up (healthy)
project-frontend-1   project-frontend   frontend   Up (healthy)
```

### Step 6: Test the health endpoint

```bash
curl http://localhost:8000/health
```

Expected output:

```json
{"status":"ok","arango":"connected","redis":"connected"}
```

If arango shows `"unavailable"`, restart the backend:

```bash
docker compose restart backend
```

Then test again after 5 seconds.

### Step 7: Open in browser

| What | URL |
|------|-----|
| Frontend (React UI) | http://localhost:3000 |
| Backend API docs (Swagger) | http://localhost:8000/docs |
| ArangoDB admin UI | http://localhost:8529 (user: `root`, password: empty) |

### Step 8: Stop all services

```bash
docker compose down
```

To also delete all data (reset database):

```bash
docker compose down -v
```

---

## Run without Docker (optional)

Only if you need to run services individually on your host machine.

### Backend only

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --port 8000 --reload

# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn backend.app.main:app --port 8000 --reload
```

Backend starts on http://localhost:8000. ArangoDB and Redis must be running separately for full functionality.

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

Frontend starts on http://localhost:3000. Proxies `/api` requests to backend on port 8000.

---

## Ollama setup (local LLM — optional for now)

Ollama runs on the host machine (not inside Docker).

### macOS

```bash
brew install ollama
ollama serve
ollama pull qwen2.5:3b
```

### Windows

Download from https://ollama.com/download. Install and run, then:

```bash
ollama pull qwen2.5:3b
```

### Verify

```bash
ollama list
```

Expected: `qwen2.5:3b` appears in the list.

See [docs/ollama-setup.md](docs/ollama-setup.md) for full details.

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health status |
| `GET` | `/api/tickets` | List all tickets |
| `POST` | `/api/tickets` | Create a ticket (body: `{"title":"...","description":"...","priority":"low\|medium\|high"}`) |
| `GET` | `/api/tickets/{id}` | Get a single ticket |
| `DELETE` | `/api/tickets/{id}` | Delete a ticket |

Interactive docs: http://localhost:8000/docs

---

## Environment variables

Loaded from `.env` file via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). See `.env.example` for all variables with comments.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API server |
| `OLLAMA_MODEL` | `qwen2.5:3b` | LLM model tag |
| `ARANGO_URL` | `http://localhost:8529` | ArangoDB endpoint |
| `ARANGO_DB` | `ticket_agent` | Database name |
| `ARANGO_USER` | `root` | Database user |
| `ARANGO_PASSWORD` | *(empty)* | Database password |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `CONFIDENCE_THRESHOLD` | `0.70` | Routing confidence threshold |
| `LOG_LEVEL` | `INFO` | Log level |

Environment variables always override `.env` file values.

---

## Repository layout

```
backend/
  app/main.py          FastAPI entry point (uvicorn backend.app.main:app)
  api/health.py        GET /health endpoint
  api/tickets.py       Tickets CRUD API
  api/router.py        Central router
  core/config.py       Pydantic Settings (reads .env)
  services/database.py ArangoDB connection helper
  services/cache.py    Redis connection helper
  schemas/ticket.py    Request/response schemas
  Dockerfile           Python 3.12-slim, multi-stage
frontend/
  src/App.jsx          Root component
  src/components/      TicketForm, TicketList, StatusBar
  src/services/api.js  Backend API client
  vite.config.js       Vite dev server + proxy config
  Dockerfile           Node 20-slim, multi-stage
  package.json         React 19, Vite 6
docker-compose.yml     All 4 services: ArangoDB, Redis, backend, frontend
.env.example           Environment variable template
scripts/setup-ollama.sh  Automated Ollama install script
docs/ollama-setup.md   Ollama setup guide
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `docker: command not found` | Install Docker Desktop and make sure it is running |
| `port already in use` | Stop other services on ports 3000, 8000, 6379, 8529 |
| Backend health shows arango `"unavailable"` | Run `docker compose restart backend` |
| Frontend shows "Could not load tickets" | Wait 10 seconds for backend to start, then refresh |
| `docker compose up` is slow first time | Normal — downloads ~3 GB. Cached after first build |
| ArangoDB shows `(unhealthy)` | Wait 30 seconds — it initializes the database on first run |

## Branching (GitHub Flow)

- `main` — protected; always release-ready. PR + 1 review required.
- `feature/*`, `fix/*`, `chore/*` — short-lived branches off `main`, merged back via PR.

## Tracking

Issues tracked in Jira project **ATR** on `nasscomrag.atlassian.net`.
