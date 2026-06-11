# Phase 3: Seed Data & Synthetic Ticket Generation

## What We Did

Created the initial data that populates DeskMind's knowledge graph, then generated 800 synthetic tickets for training the AI classifiers.

## Why We Need Seed Data

Without data, DeskMind is an empty shell:
- KNN classifier has no past tickets to compare against
- Centroid classifier has no averages to compute
- Graph traversal finds nothing (no edges)
- Vector search returns nothing (no embeddings)

Seed data gives the system enough knowledge to work from day one.

---

## Part 1: Seed Data (seed_data.yaml)

**File**: `data/seed/seed_data.yaml` (1,667 lines)

This is a hand-crafted YAML file containing a realistic fake IT infrastructure:

### What's in it:

| Section | Count | Example |
|---------|-------|---------|
| **Teams** | 6 | Infrastructure Ops, Database Admin, Access Management, etc. |
| **Servers** | 15 | prod-db-01 (database, ap-south-1, 32GB RAM), prod-web-01, etc. |
| **Services** | 12 | PostgreSQL 15.4 (port 5432), Redis 7.2, NGINX, Kubernetes, etc. |
| **Engineers** | 12 | 2 per team — Indian names, 4 Muslim names (Arjun Nair, Ayesha Khan, etc.) |
| **Network devices** | 5 | fw-prod-01 (Palo Alto firewall), lb-web-01 (F5 load balancer), etc. |
| **Error codes** | 20 | ERR-PG-001 "FATAL: too many connections", ERR-K8S-001 "OOMKilled", etc. |
| **Runbooks** | 10 | KB-0001 "PostgreSQL connection limit exceeded" with step-by-step fix |
| **Routing rules** | 24 | 6 categories x 4 priorities → which team handles each |
| **Tickets** | 55 | Historical resolved tickets across all 6 categories |
| **Resolutions** | 30 | Fix steps linked to tickets, with effectiveness scores |
| **Manual edges** | 55 | hosts, managed_by, depends_on, member_of |

### Key design decisions:
- **Datacenters**: ap-south-1 (Mumbai, primary), ap-south-2 (Hyderabad, secondary) — AWS naming style
- **Categories**: Infrastructure, Application, Database, Network, Security, **Access Management**
- **New fields added for improved architecture**: `quality_score`, `secondary_category`, `classifier_votes` on all 55 tickets
- **9 tickets have secondary_category** (ambiguous tickets like "Firewall blocking database port")

---

## Part 2: Synthetic Ticket Generation (800 tickets)

### Why generate synthetic data?

55 hand-crafted tickets isn't enough for:
- KNN to have good coverage (need ~100+ per category)
- Centroids to be accurate (more data = better averages)
- Training the AI to handle diverse writing styles

### Generation Strategy

We used **3 different strategies** to create diverse, realistic tickets:

#### Strategy 1: Multi-model generation (600 tickets)

**Idea**: Different AI models have different writing styles. Using multiple models gives us more diverse training data.

| Model | How | Tickets generated |
|-------|-----|------------------|
| **GPT-4o** (OpenAI API) | Script calls API with prompts | 396 |
| **Claude** (Claude API) | High-quality tickets generated via Claude API | 164 |
| **Phi-4-mini** (local Ollama) | Script calls local model | 13 (unreliable JSON output) |

**3 Personas per model**: Each model generated tickets in 3 different writing styles:

| Persona | Style | Example |
|---------|-------|---------|
| **Frustrated user** | Messy, emotional, non-technical | "HELP!! email not loading… meeting in 10 min… pls fix" |
| **L2 Engineer** | Technical, logs, timestamps | "prod-db-02 FATAL: too many connections at 2026-04-14T03:22Z. Pool 47/50." |
| **Manager** | Business impact, asks for ETA | "Sales team can't access CRM. Impacting quarterly close." |

**Scripts**:
- `scripts/generate_tickets.py` — calls GPT-4o API (and Phi-4-mini locally). Uses `--openai-key` argument. Generates in batches of 25.
- `scripts/generate_claude_tickets.py` — first batch of Claude-style templates (99 tickets)
- `scripts/generate_claude_tickets_batch2.py` — second batch (92 more templates)

#### Strategy 2: Template + noise injection (200 tickets)

**Idea**: Create structured templates then add realistic noise — typos, abbreviations, irrelevant info. Teaches the AI to handle messy real-world input.

**Script**: `scripts/generate_noise_tickets.py` — no LLM needed, pure Python.

**Noise types injected**:
- Typos: "please" → "plese", "server" → "servr"
- ALL CAPS for emphasis
- Irrelevant info: "(my laptop is Dell btw)", "[sent from iPhone]"
- Extra punctuation: "!!!" instead of "."

#### Strategy 3: Real-world + edge cases (200 tickets — planned, not yet done)

- 170 manual/team-written tickets
- 30 ambiguous edge case tickets for evaluation

### Output files:

```
data/synthetic/
  strategy1_multimodel/
    gpt4o_tickets.json         (198 tickets)
    gpt4o_tickets_batch2.json  (198 tickets)
    claude_tickets.json        (164 tickets)
    phi4_tickets.json          (13 tickets)
  strategy2_noise/
    noise_tickets.json         (200 tickets)
  final/
    all_generated_tickets.json (800 tickets — combined, deduplicated)
```

### Validation done on all 800 tickets:
- Zero duplicate titles (36 duplicates found and fixed)
- All categories valid (6 categories only)
- All priorities valid (critical/high/medium/low)
- All server/service/error_code references match seed_data.yaml
- All runbook references valid
- Zero missing required fields
- Average description length: 154 chars

---

## Part 3: Loading Data (seed_db.py)

**File**: `scripts/seed_db.py`

This script loads **everything** into ArangoDB in one run (~40 seconds).

### What it does step by step:

**Step 1**: Connect to ArangoDB at localhost:8530

**Step 2**: Truncate all collections (clean slate — safe to run multiple times)

**Step 3**: Load MiniLM embedding model (all-MiniLM-L6-v2, 384 dimensions)

**Step 4**: Load infrastructure from seed_data.yaml:
- 6 teams → `teams` collection
- 15 servers → `servers` collection
- 12 services → `services` collection
- 12 engineers → `engineers` collection
- 5 network devices → `network_devices` collection
- 20 error codes → `error_codes` collection
- 10 runbooks → `runbooks` collection (with embeddings)
- 24 routing rules → `routing_rules` collection
- 55 manual edges (hosts, managed_by, depends_on, member_of)

**Step 5**: Load all 855 tickets (55 seed + 800 synthetic):
- Compute 384-dim embedding for each ticket description
- Insert into `tickets` collection

**Step 6**: Load 830 resolutions:
- Compute embeddings for resolution steps
- Create `resolved_with` edges (ticket → resolution)
- Create `references` edges (resolution → runbook)

**Step 7**: Create auto-edges for ALL 855 tickets:
- `affects` edges: 1,425 (ticket → server/service)
- `assigned_to` edges: 855 (ticket → team, via routing rules)
- `triggered_by` edges: 396 (error_code → ticket)

**Step 8**: Compute category centroids:
- Group all tickets by category
- Average their embeddings → one 384-dim centroid per category
- Save to `category_centroids` (6 entries)

### Final numbers:

| Metric | Count |
|--------|-------|
| Document nodes | 1,795 |
| Edge connections | 3,831 |
| Tickets with embeddings | 855 |
| Resolutions with embeddings | 830 |
| Runbooks with embeddings | 10 |
| Category centroids | 6 |
| Total processing time | ~40 seconds |

### How to run:
```bash
source .venv/bin/activate
python scripts/seed_db.py
```

### Important notes for developers:
- Script is **idempotent** — truncates everything and reloads. Safe to run multiple times.
- Requires Python venv with sentence-transformers, pyyaml, tqdm installed
- ArangoDB must be running on port 8530
- First run downloads MiniLM model (~90MB, cached after that)
