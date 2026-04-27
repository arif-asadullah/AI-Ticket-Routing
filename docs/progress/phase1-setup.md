# Phase 1: Project Setup

## What We Did

Set up the entire development environment from scratch so the team can run DeskMind with one command.

## Step by Step

### 1. Environment Configuration (ATR-5)

**What**: Created `.env.example` and `.env` files with all configuration variables.

**Why**: Every service (ArangoDB, Redis, Ollama) needs connection details. Instead of hardcoding them, we put them in a `.env` file that each developer configures locally.

**Files created**:
- `.env.example` — template with comments explaining each variable
- `.env` — local copy (gitignored, never committed)
- `backend/core/config.py` — Pydantic Settings class that reads `.env` automatically

**Key variables**:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
ARANGO_URL=http://localhost:8530
ARANGO_DB=ticket_agent
REDIS_URL=redis://localhost:6379
EMBEDDING_MODEL=all-MiniLM-L6-v2
CONFIDENCE_THRESHOLD=0.70
```

### 2. Docker Compose (ATR-6, ATR-7, ATR-8)

**What**: Created `docker-compose.yml` with 4 services that start with one command.

**Why**: Nobody wants to install ArangoDB, Redis, Python, and Node.js manually. Docker runs everything in containers.

**Services**:
| Service | Port | What it does |
|---------|------|-------------|
| ArangoDB | 8530 | Graph + vector database |
| Redis | 6379 | Caching |
| FastAPI backend | 8000 | API server |
| React frontend | 3000 | Web UI |

**Files created**:
- `docker-compose.yml` — all 4 services with health checks and volumes
- `backend/Dockerfile` — Python 3.12, installs requirements, runs uvicorn
- `frontend/Dockerfile` — Node 20, installs npm packages, runs Vite dev server

**How to use**: `docker compose up --build`

### 3. Ollama Setup (ATR-9, ATR-10)

**What**: Installed Ollama on the Mac and pulled the LLM model.

**Why**: DeskMind uses a local LLM (not cloud API) for ticket classification. Ollama is the runtime that serves the model.

**Model history**:
- Started with Phi-3-mini (3.8B params)
- Used Phi-4-mini temporarily for data generation
- Switched to **Qwen 2.5:3B** for production (smaller, faster, fits 8GB RAM)

**Files created**:
- `scripts/setup-ollama.sh` — automated install script for teammates
- `docs/ollama-setup.md` — manual setup guide

**How Ollama connects**: Ollama runs on the Mac (not in Docker). The backend inside Docker reaches it via `host.docker.internal:11434`.

### 4. Backend Scaffold

**What**: Created the FastAPI backend with health check, ticket CRUD, and chat endpoints.

**Files created**:
- `backend/app/main.py` — FastAPI app with lifespan (connects to ArangoDB + Redis on startup)
- `backend/api/health.py` — `GET /health` endpoint
- `backend/api/tickets.py` — Ticket CRUD API (later replaced with AI pipeline)
- `backend/api/chat.py` — Chat with Ollama endpoint
- `backend/services/database.py` — ArangoDB connection helper
- `backend/services/cache.py` — Redis connection helper
- `backend/services/llm.py` — Ollama chat client

### 5. Frontend Scaffold

**What**: Created the React frontend with Vite.

**Files created**:
- `frontend/package.json` — React 19, Vite 6
- `frontend/vite.config.js` — Dev server config with API proxy
- `frontend/src/App.jsx` — Main app component
- `frontend/index.html` — Entry point with DeskMind favicon

### 6. SSH Key + Git Config

**What**: Set up SSH key for permanent GitHub authentication. Set git user to Arif Asadullah.

**Why**: HTTPS auth required credentials every push. SSH key means push without password forever.

**What was done**:
- Generated ed25519 SSH key
- Added to GitHub account
- Configured `~/.ssh/config` with macOS keychain
- Set `git config --global user.name "Arif Asadullah"`
