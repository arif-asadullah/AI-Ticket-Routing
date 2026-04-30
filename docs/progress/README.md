# DeskMind — Project Progress

This folder documents everything we've built, step by step, so any developer can understand what was done, why, and how to work with it.

## Project Summary

**DeskMind** is an AI-powered IT ticket routing system that:
1. Receives a support ticket from a user
2. Uses 4 independent AI classifiers to determine which team should handle it
3. Finds similar past tickets and suggests resolutions
4. Routes the ticket to the correct team automatically

## What's Been Built

| Phase | What | Status |
|-------|------|--------|
| [Phase 1: Setup](phase1-setup.md) | Docker, env config, Ollama, SSH, project scaffold | Done |
| [Phase 2: Schema](phase2-schema.md) | 13 collections, 9 edge collections, graph, indexes, vector search | Done |
| [Phase 3: Seed Data](phase3-seed-data.md) | 855 tickets loaded, 800 synthetic generated, 1796 nodes, 3831 edges | Done |
| [Phase 4: Classification](phase4-classification.md) | 4-classifier ensemble pipeline: LLM + KNN + Centroid + Keywords | Done |
| [Phase 5: Frontend](phase5-frontend.md) | Neural Dark theme, landing page, ticket form, chat AI | Done |
| [Phase 6: Ticket Lifecycle](phase6-ticket-lifecycle.md) | Full lifecycle: status updates, resolve, resolution suggestions, Jira cleanup | Done |
| [Phase 7: Auth & RBAC](phase7-rbac-auth.md) | JWT auth, 3 roles (admin/engineer/viewer), team-scoped access, user management UI | Done |

## Tech Stack

| Technology | What it does |
|-----------|-------------|
| **FastAPI** | Backend API server (Python) |
| **React + Vite** | Frontend UI |
| **ArangoDB** | Graph + document + vector database |
| **Redis** | Caching |
| **Qwen 2.5:3B (Ollama)** | Local LLM for ticket classification |
| **MiniLM (sentence-transformers)** | Converts ticket text to 384-dim embeddings |
| **Docker Compose** | Runs all services together |

## How to Run

```bash
# Start all services
docker compose up --build -d

# Load data into database (first time only)
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_db.py

# Start Ollama (on your Mac, not in Docker)
open /Applications/Ollama.app

# Open in browser
http://localhost:3000
```

## Key Numbers

| Metric | Count |
|--------|-------|
| Document collections | 13 |
| Edge collections | 9 |
| Total tickets in DB | 855 |
| Resolutions | 830 |
| Category centroids | 6 |
| Graph edges | 3,831 |
| Classifiers in ensemble | 4 |
| Target accuracy | ~90%+ |

## Reading Order

If you're new to the project, read in this order:
1. This README (you're here)
2. Phase 1 — understand the setup
3. Phase 2 — understand the database
4. Phase 3 — understand the data
5. Phase 4 — understand the AI pipeline (most important)
6. Phase 5 — understand the UI
7. Phase 6 — understand the ticket lifecycle (status, resolve, feedback loop)
8. Phase 7 — understand authentication and RBAC (roles, team-scoping, JWT)

For architecture details, see `docs/architecture/`.
For database schema details, see `docs/schema/`.
For Nasscom R2 submission documents, see `docs/nasscom-r2/`.
