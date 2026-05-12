# DeskMind — Data Sources & Data Engineering

> **Nasscom Agentic AI Hackathon — Round 2 Submission**

---

## 1. Data Sources Overview

DeskMind uses **5 data sources** to build its knowledge graph and train its classifiers:

| # | Source | Type | Records | Generation Method |
|---|--------|------|---------|-------------------|
| 1 | Seed Data (YAML) | Hand-crafted | 55 tickets + infrastructure graph | Manual design by team |
| 2 | GPT-4o Generated | AI-generated | 396 tickets | OpenAI API with category-specific prompts |
| 3 | Claude Hand-crafted | AI-generated | 191 tickets | Hand-crafted edge cases and complex scenarios |
| 4 | Noise Generator | Programmatic | 200 tickets | Python template + noise injection script |
| 5 | User Submissions | Runtime | Growing | Live tickets submitted through the frontend |

**Total training data**: 855 tickets (55 seed + 800 synthetic)

---

## 2. Data Source Details

### 2.1 Seed Data — Infrastructure Knowledge Graph

**File**: `data/seed/seed_data.yaml`

Hand-crafted YAML containing the **core infrastructure topology** that forms the knowledge graph:

| Entity | Count | Purpose |
|--------|-------|---------|
| Teams | 6 | One per IT domain (Infrastructure Ops, Application Support, Database Admin, Network Operations, Security Operations, Access Management) |
| Engineers | 12 | 2 per team with expertise areas and skills |
| Servers | 15 | Physical/virtual machines across ap-south-1 and ap-south-2 datacenters |
| Services | 12 | Software (PostgreSQL, Redis, Nginx, Kubernetes, etc.) with versions and ports |
| Network Devices | 5 | Firewalls, switches, routers, load balancers |
| Error Codes | 20 | Known error patterns with regex, severity, and associated service |
| Runbooks | 10 | Step-by-step procedures for common issues |
| Routing Rules | 24 | Maps {category, priority} → team (4 rules per category) |
| Tickets | 55 | Representative tickets across all 6 categories |
| Resolutions | 30 | Documented fixes linked to tickets |
| Edges | 55 | Manual relationships (hosts, managed_by, affects, depends_on, etc.) |
| Users | 1 | Admin account (additional users created via UI at runtime) |

**Why hand-crafted**: The infrastructure topology must be internally consistent — servers must host the right services, teams must manage the right servers, error codes must reference real services. AI-generated data tends to have cross-reference inconsistencies.

### 2.2 GPT-4o Generated Tickets

**Script**: `scripts/generate_tickets.py`
**Output**: `data/synthetic/gpt4o/` (396 tickets)

**Method**:
1. Category-specific system prompts define the scope and expected detail level
2. 3 persona variations per category:
   - **Frustrated end user**: Non-technical, typos, abbreviations, describes symptoms
   - **L2 engineer**: Precise, includes hostnames, timestamps, log snippets, error codes
   - **Vague manager**: Formal, describes business impact, no technical details
3. Generated in batches of 25 tickets via OpenAI Chat Completions API
4. Each ticket includes: title, description, category, priority, error_codes, server_names, service_names

**Category distribution**:
| Category | Target % | Tickets |
|----------|----------|---------|
| Infrastructure | 30% | ~119 |
| Application | 25% | ~99 |
| Database | 15% | ~59 |
| Network | 12% | ~48 |
| Security | 10% | ~40 |
| Access Management | 8% | ~32 |

**Why imbalanced**: Mirrors real-world IT ticket distribution where Infrastructure and Application tickets dominate.

### 2.3 Claude Hand-Crafted Tickets

**Output**: `data/synthetic/claude/` (191 tickets)

**Method**: Manually crafted by the team using Claude as a writing assistant. Focus on:
- **Edge cases**: Tickets that span two categories (e.g., "database issue caused by network timeout")
- **Ambiguous tickets**: Vague descriptions that test the system's escalation logic
- **Multi-hop scenarios**: Issues requiring graph traversal to identify root cause
- **Realistic error messages**: Actual PostgreSQL, Kubernetes, Nginx error snippets

### 2.4 Noise Generator — Template + Injection

**Script**: `scripts/generate_noise_tickets.py`
**Output**: `data/synthetic/noise/` (200 tickets)

**Method**: Python-based template engine with realistic noise injection:

```
Template: "[SEVERITY] [SYSTEM] - [SYMPTOM]. [CONTEXT]."
Word banks per category → fill templates → apply noise
```

**Noise types applied**:
| Noise Type | Rate | Example |
|-----------|------|---------|
| Adjacent letter swaps | 5% of words | "server" → "srevr" |
| Abbreviation replacement | 30% chance | "please" → "pls", "environment" → "env" |
| Sentence truncation | 10% of tickets | Cut mid-sentence |
| Irrelevant details | 15% of tickets | "my laptop is Dell btw" |
| Mixed case | 20% of tickets | "URGENT" vs "urgent" |
| Copy-paste artifacts | 10% of tickets | Extra `\n\t` characters |

**Why we need noise**: LLM-generated tickets are unnaturally clean. Real user input has typos, abbreviations, and irrelevant information. The noise generator tests classifier robustness.

### 2.5 User Submissions (Runtime)

Tickets submitted through the DeskMind frontend at runtime. Tagged with `_source: "user"` to distinguish from training data. Each user ticket:
- Gets a 384-dim MiniLM embedding
- Gets classified by the 4-classifier ensemble
- Gets stored with full classification metadata
- Creates `assigned_to` edges in the knowledge graph
- Gets logged in `audit_log` collection

---

## 3. Data Engineering Pipeline

### 3.1 Ingestion Pipeline

```
                    ┌──────────────────┐
                    │  Raw Data Sources │
                    │                  │
                    │  seed_data.yaml  │
                    │  gpt4o/*.json    │
                    │  claude/*.json   │
                    │  noise/*.json    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  scripts/seed_db │
                    │      .py         │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐ ┌───▼────┐ ┌───────▼────────┐
     │   Validate &   │ │ Embed  │ │  Build Graph   │
     │   Normalize    │ │ (MiniLM│ │   Edges        │
     │                │ │  384d) │ │                │
     │- Fix null lists│ │        │ │- hosts         │
     │- Ensure fields │ │        │ │- managed_by    │
     │- Category check│ │        │ │- affects       │
     │- Dedup titles  │ │        │ │- depends_on    │
     └────────┬───────┘ └───┬────┘ │- triggered_by  │
              │              │      │- assigned_to   │
              │              │      │- resolved_with │
              │              │      │- references    │
              │              │      │- member_of     │
              │              │      └───────┬────────┘
              └──────────────┼──────────────┘
                             │
                    ┌────────▼─────────┐
                    │  ArangoDB Insert │
                    │                  │
                    │  1,796 documents │
                    │  3,831 edges     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Compute Centroids│
                    │                  │
                    │ avg(embedding)   │
                    │ per category     │
                    │ → 6 centroids    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Load Users      │
                    │                  │
                    │ Hash passwords   │
                    │ (bcrypt)         │
                    │ → admin account  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Create Indexes  │
                    │                  │
                    │ - Vector index   │
                    │ - Fulltext index │
                    │ - Persistent idx │
                    │ - Unique (email) │
                    └──────────────────┘
```

### 3.2 Data Validation Steps

The ingestion script performs these validation checks:

| Check | What it does | Action on failure |
|-------|-------------|-------------------|
| Category validation | Ensures category is one of 6 valid values | Skip ticket |
| Field presence | All required fields exist (title, description, category) | Skip ticket |
| List field normalization | Converts null/string fields to empty lists | Auto-fix |
| Description length | Minimum 20 characters | Skip ticket |
| Duplicate detection | Title uniqueness across all sources | Skip duplicate |
| Cross-reference validation | Servers, services, error codes referenced in tickets exist in their collections | Log warning |
| Embedding dimensionality | All embeddings are exactly 384 dimensions | Recompute |

### 3.3 Embedding Generation

**Model**: `all-MiniLM-L6-v2` (Sentence Transformers)
**Dimensions**: 384
**What gets embedded**:
- Every ticket's `description` field → stored in `tickets.embedding`
- Every resolution's `steps` joined as text → stored in `resolutions.embedding`

**Centroid computation**:
```python
for category in ["Infrastructure", "Application", "Database", "Network", "Security", "Access Management"]:
    tickets_in_category = all tickets where category == category
    centroid = mean(all embeddings in tickets_in_category)
    save to category_centroids collection
```

### 3.4 Index Creation

| Index Type | Collection | Field(s) | Purpose |
|-----------|-----------|----------|---------|
| Vector (APPROX_NEAR_COSINE) | tickets | embedding (384d) | Semantic similarity search |
| Fulltext | tickets | description | Keyword search |
| Persistent | tickets | category, status, _source | Filter queries |
| Persistent | audit_log | ticket_id | Audit trail lookup |
| Persistent | routing_rules | category, priority, is_active | Team routing lookup |
| Persistent (unique) | users | email | Fast login lookup, prevent duplicates |

**Vector index note**: ArangoDB 3.12 requires `--vector-index true` flag at startup. The vector subsystem takes ~10 seconds to initialize, so `schema.py` uses a retry loop (5 attempts, 5s delay) when creating vector indexes.

---

## 4. Data Quality Metrics

| Metric | Value |
|--------|-------|
| Total unique tickets | 855 |
| Category coverage | All 6 categories represented |
| Min tickets per category | ~105 (Security) |
| Max tickets per category | ~168 (Infrastructure) |
| Tickets with error codes | ~40% |
| Tickets with server names | ~60% |
| Tickets with noise | ~23% (200/855) |
| Cross-reference integrity | 100% (all edges point to valid documents) |
| Embedding coverage | 100% (all tickets have 384-dim embeddings) |
| **Labels verified** | **48 mislabeled tickets corrected** (6 rounds of eval-driven cleanup) |
| **Eval accuracy** | **83.7%** on 50-ticket held-out set |

### 4.1 Label Quality Cleanup

After building the eval script (`scripts/eval_classifier.py`), we discovered 48 synthetic tickets with wrong category labels. These were generated by GPT-4o, Claude, and the noise generator with incorrect category assignments. Examples:

| Ticket | Was | Fixed To | Why |
|--------|-----|----------|-----|
| "LDAP Service Synchronization Error" | Application | Access Management | LDAP is identity/access |
| "Redis Cache Saturation" | Application | Database | Redis is a database |
| "Kubernetes Pod Not Scheduling" | Application | Infrastructure | K8s scheduling is infra |
| "Can't login to system" | Security | Access Management | Login issue ≠ security breach |
| "Grafana dashboards empty" | Infrastructure | Application | Grafana is an application |

These were fixed iteratively — run eval → find misclassifications → determine if label or AI is wrong → fix labels → re-eval. 6 rounds brought accuracy from 78% to 83.7%. 3 seed data tickets were also corrected.

---

## 5. Data Growth Strategy

As DeskMind processes real tickets:
1. **New ticket** → embedded + classified + stored → knowledge graph grows
2. **Resolution submitted** → embedded + linked → future suggestions improve
3. **AI suggestion confirmed** → effectiveness score updated → ranking improves
4. **Category centroids** → recomputed periodically → classification adapts
5. **User-resolved tickets feed back into retrieval** → the vector similarity search now includes tickets with status `"resolved"` (not just `"closed"`), so engineer-resolved incidents immediately become available as context for classifying and suggesting resolutions for new tickets. The AQL filter is `FILTER ticket.status IN ["closed", "resolved"]`.
6. **Feedback ratings** → users rate AI suggestions via `POST /api/tickets/{id}/feedback` as helpful or not_helpful. These ratings are logged in the audit trail and surfaced in the analytics dashboard, enabling continuous monitoring of AI suggestion quality.

This creates a **live feedback loop**: more resolved tickets → better suggestions → faster resolution → more confirmed suggestions → higher suggestion quality over time.
