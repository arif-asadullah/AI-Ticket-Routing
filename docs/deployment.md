# Setup and Deployment Guide

Complete guide for setting up DeskMind from scratch. A new team member should be able to get the system running using only this document.

---

## Prerequisites

| Tool | Version | Required | Install |
|------|---------|----------|---------|
| Docker Desktop | 28+ | Yes | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Git | 2.30+ | Yes | Pre-installed on macOS/Linux; [git-scm.com](https://git-scm.com/) for Windows |
| Ollama | Latest | Yes (for LLM) | [ollama.com/download](https://ollama.com/download) |
| Node.js | 20+ | Only for local frontend dev | [nodejs.org](https://nodejs.org/) |
| Python | 3.12+ | Only for local backend dev | [python.org](https://www.python.org/) |

**System requirements:**
- RAM: 8 GB minimum (ArangoDB + Redis + Backend + Ollama)
- Disk: 5 GB free (Docker images + model weights)
- OS: macOS (Intel/Apple Silicon), Windows 10/11 (WSL2), Linux

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/arif-asadullah/AI-Ticket-Routing.git
cd AI-Ticket-Routing
```

---

## Step 2: Environment Variables

```bash
cp .env.example .env
```

The defaults work for local development. For production, edit `.env`:

```bash
# Required — change for production
ARANGO_PASSWORD=your-secure-password

# Optional — tune as needed
OLLAMA_BASE_URL=http://localhost:11434    # host machine Ollama
OLLAMA_MODEL=qwen2.5:7b                  # 7B is the benchmarked default; qwen2.5:3b is lighter but less accurate
CONFIDENCE_THRESHOLD=0.70                 # lower = more auto-routing, higher = more escalation
LOG_LEVEL=INFO                            # DEBUG for troubleshooting
```

**Full variable reference:**

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:7b` | LLM model for classification |
| `ARANGO_URL` | `http://localhost:8530` | ArangoDB endpoint |
| `ARANGO_DB` | `ticket_agent` | Database name |
| `ARANGO_USER` | `root` | Database user |
| `ARANGO_PASSWORD` | *(empty)* | Database password |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `CONFIDENCE_THRESHOLD` | `0.70` | Auto-route threshold |
| `LOG_LEVEL` | `INFO` | Python log level |

---

## Step 3: Install and Start Ollama

Ollama runs on the **host machine** (not inside Docker) because it needs GPU/CPU access for inference.

### macOS

```bash
brew install ollama
ollama serve                  # start the server (keep running)
ollama pull qwen2.5:7b        # download model (~4.7 GB)
```

### Windows

1. Download from [ollama.com/download](https://ollama.com/download)
2. Run installer
3. Open terminal:

```bash
ollama pull qwen2.5:7b
```

### Verify Ollama

```bash
curl http://localhost:11434/api/version
```

Expected: `{"version":"..."}` (any version string means it's running)

---

## Step 4: Start All Services

```bash
docker compose up --build -d
```

**First run:** Downloads ~3 GB of images. Takes 5-10 minutes.
**Subsequent runs:** Takes seconds (cached).

### Verify all services are healthy

```bash
docker compose ps
```

All 4 should show **(healthy)**:

```
NAME                 SERVICE    STATUS
project-arangodb-1   arangodb   Up (healthy)
project-redis-1      redis      Up (healthy)
project-backend-1    backend    Up (healthy)
project-frontend-1   frontend   Up (healthy)
```

### Verify health endpoint

```bash
curl http://localhost:8000/health
```

Expected:

```json
{
  "status": "ok",
  "arango": "connected",
  "redis": "connected",
  "ollama": "connected",
  "degradation_level": 4,
  "message": "All systems operational"
}
```

If `degradation_level` < 4, check which service is down and restart it.

---

## Step 5: Initialize and Seed the Database

The database schema (collections, edges, indexes, graph) is auto-created on backend startup. But you need to seed it with data:

```bash
docker compose exec backend python scripts/seed_db.py
```

This loads:
- 6 teams with SLA definitions
- 12 engineers with skills
- 15 servers, 12 services, 5 network devices
- 20 error codes with patterns
- 24 routing rules
- 55 curated seed tickets (with embeddings)
- 800 synthetic tickets (with embeddings)
- 10 runbooks
- 1 admin user account
- Category centroid vectors

**Expected output:**

```
Loading seed data...
  teams: 6
  engineers: 12
  servers: 15
  ...
  users: 1 accounts (passwords hashed)
Computing category centroids...
Done! Loaded 855 tickets with embeddings.
```

---

## Step 6: Access the Application

| Service | URL | Credentials |
|---------|-----|-------------|
| DeskMind UI | http://localhost:3000 | `arif.asadullah@schwettmann.in` / `DeskMind@2026` |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| ArangoDB Admin | http://localhost:8530 | `root` / *(empty)* |

---

## Step 7: Create Your First Ticket

### Via the UI

1. Log in at http://localhost:3000
2. Click "New Ticket" (+ button in header)
3. Fill in title, description, priority
4. Click Submit — watch the 4 classifiers run in real-time
5. See the ticket appear on the dashboard with classification result

### Via API

```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"arif.asadullah@schwettmann.in","password":"DeskMind@2026"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create a ticket
curl -X POST http://localhost:8000/api/tickets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Production server unresponsive",
    "description": "prod-app-01 has been down since 6 AM. No SSH access, ping times out.",
    "priority": "critical"
  }'
```

---

## Running the Test Suite

The repo ships a 68-function pytest unit suite (`tests/unit/` — aggregator, knn,
keyword, quality_scorer, circuit_breaker, find_runbook). These are correctness
unit tests; they do **not** produce the accuracy figure:

```bash
docker compose exec backend python scripts/seed_db.py    # ensure data is loaded
docker compose exec backend python -m pytest tests/ -v    # run unit test suite
```

> **Note:** This suite is **not** run in CI (there is no `.github/workflows`
> configuration). Run it locally before pushing.

### Accuracy benchmark

The 94.1% classification accuracy is produced by the evaluation scripts, **not**
by pytest. Run them against the fixed benchmark set:

```bash
docker compose exec backend python scripts/evaluate.py          # full ensemble eval
docker compose exec backend python scripts/eval_classifier.py   # per-classifier eval
```

These score against `data/eval/test_tickets.json`.

---

## Docker Commands Reference

| Command | Description |
|---------|-------------|
| `docker compose up --build -d` | Start all services (rebuild if needed) |
| `docker compose ps` | Check service status |
| `docker compose logs backend --tail 50` | View backend logs |
| `docker compose logs -f` | Follow all logs live |
| `docker compose restart backend` | Restart just the backend |
| `docker compose down` | Stop all services |
| `docker compose down -v` | Stop + delete all data (full reset) |
| `docker compose exec backend python scripts/seed_db.py` | Seed the database |

---

## Stopping and Restarting

### Stop (keep data)

```bash
docker compose down
```

### Stop and reset (delete all data)

```bash
docker compose down -v
```

Then re-seed after restart:

```bash
docker compose up --build -d
# Wait for healthy
docker compose exec backend python scripts/seed_db.py
```

---

## Production Deployment Notes

For deploying beyond local development:

1. **Set a real ArangoDB password** in `.env`
2. **Use a reverse proxy** (nginx/Caddy) in front of the frontend and backend
3. **Enable HTTPS** — update CORS origins in `backend/app/main.py`
4. **Ollama on GPU** — significantly faster classification with CUDA/Metal
5. **Redis persistence** — enable AOF or RDB snapshots for SLA timer durability
6. **Kubernetes** — see `k8s/` directory for manifests

---

## Troubleshooting FAQ

### 1. Backend shows `arango: unavailable`

ArangoDB takes 15-30 seconds to initialize on first run. Restart the backend:

```bash
docker compose restart backend
```

### 2. Login fails or returns 401 intermittently

Rebuild the backend to get the latest bcrypt fix:

```bash
docker compose up -d --build backend
docker compose exec backend python scripts/seed_db.py  # re-seed user
```

### 3. Classification takes very long (>60s)

- **First request** is slow (~15s) because the embedding model loads into memory
- **Subsequent requests** are faster (~10-15s) or instant if cached
- Check Ollama is running: `curl http://localhost:11434/api/version`
- If Ollama is down, system degrades to 3 classifiers (no LLM)

### 4. Frontend shows "Could not load tickets"

- Backend may still be starting — wait 10 seconds and refresh
- Check: `curl http://localhost:8000/health`
- If health fails: `docker compose logs backend --tail 20`

### 5. Port already in use

Another service is using one of the required ports (3000, 8000, 6379, 8530):

```bash
# Find what's using the port (macOS/Linux)
lsof -i :8000

# Kill it or change the port in docker-compose.yml
```

### 6. Docker build fails with "no space left on device"

```bash
docker system prune -a    # removes unused images/containers
```

### 7. Ollama model download stuck

```bash
ollama rm qwen2.5:7b      # remove partial download
ollama pull qwen2.5:7b    # retry
```
