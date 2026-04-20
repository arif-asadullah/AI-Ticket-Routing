# AI-Ticket-Routing

AI-powered ticket routing system using Retrieval-Augmented Generation (RAG) over a knowledge graph, with local LLM inference.

## Overview

An internal tooling project that classifies and routes incoming support tickets to the correct team/owner using:

- A **knowledge graph** of infrastructure topology, past incidents, and team ownership (ArangoDB).
- **Retrieval-Augmented Generation (RAG)** with sentence-transformer embeddings and a local LLM (Ollama).
- **FastAPI** backend, **React** frontend, **Redis** for caching.
- Role-based access control, JWT auth, TLS, and secrets management.

## Repository layout

```
backend/     FastAPI service (app, api, services, models, schemas, core)
frontend/    React app (components, pages, services, hooks)
data/        Synthetic, evaluation, and seed datasets
scripts/     One-off utilities and dev scripts
tests/       unit / integration / e2e
docs/        Architecture and operator docs
k8s/         Kubernetes manifests
```

## Branching (GitHub Flow)

- `main` — protected; always release-ready. PR + 1 review required.
- `feature/*`, `fix/*`, `chore/*` — short-lived branches off `main`, merged back via PR.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # configure local environment
```

Full setup (Docker Compose, Ollama, ArangoDB seed) — see `docs/setup.md` (coming in ATR-108).

## Environment variables

The backend is configured entirely through environment variables, loaded via
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
A `.env` file at the repository root is read automatically.

### Quick start

```bash
cp .env.example .env          # create your local config
$EDITOR .env                  # fill in ARANGO_PASSWORD at minimum
```

### Variable reference

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of the Ollama API server |
| `OLLAMA_MODEL` | `phi3:mini` | Ollama model tag for LLM completions |
| `ARANGO_URL` | `http://localhost:8529` | ArangoDB HTTP endpoint |
| `ARANGO_DB` | `ticket_agent` | ArangoDB database name |
| `ARANGO_USER` | `root` | ArangoDB user |
| `ARANGO_PASSWORD` | *(empty)* | ArangoDB password (**set this**) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model for embeddings |
| `CONFIDENCE_THRESHOLD` | `0.70` | Min cosine-similarity score for confident routing (0.0–1.0) |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

> **Precedence:** Real environment variables always override values in `.env`.
> In Kubernetes / Docker, inject variables directly; the `.env` file is for local dev only.

## Tracking

Issues tracked in Jira project **ATR** on `nasscomrag.atlassian.net`.
