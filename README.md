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
```

Full setup (Docker Compose, Ollama, ArangoDB seed) — see `docs/setup.md` (coming in ATR-108).

## Tracking

Issues tracked in Jira project **ATR** on `nasscomrag.atlassian.net`.
