# DeskMind Self-Learning System

> How DeskMind continuously improves its ticket classification accuracy without manual retraining.

---

## Overview

DeskMind doesn't just classify tickets — it **learns from every interaction**. Three feedback loops run continuously, turning human corrections, resolution outcomes, and ticket patterns into better future classifications.

```
                    ┌─────────────────────────────────┐
                    │         New Ticket Arrives       │
                    └──────────────┬──────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │   4-Classifier Ensemble          │
                    │   LLM + Centroid + KNN + Keyword │
                    └──────────────┬──────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                     Auto-Route         Escalate
                     (>70%)             (<70%)
                          │                 │
                          ▼                 ▼
                    ┌───────────┐    ┌──────────────┐
                    │  Team     │    │  Human       │
                    │  Resolves │    │  Overrides   │──── Loop 2: Correction Learning
                    └─────┬─────┘    └──────────────┘
                          │
                          ▼
                    ┌───────────────┐
                    │  Feedback     │──── Loop 1: Resolution Quality Gate
                    │  (helpful?)   │
                    └───────────────┘
                          │
                          ▼
                    ┌───────────────┐
                    │  Pattern      │──── Loop 3: Repeated Issue Detection
                    │  Analysis     │
                    └───────────────┘
```

---

## Loop 1: Resolution Quality Gate (ATR-118)

**What it does:** Learns which resolutions actually work and promotes them.

### How It Works

1. Engineer resolves a ticket with resolution steps
2. Resolution is stored with `verified: false` and an initial effectiveness score
3. User gives feedback: "Did the AI suggestion help?"
4. System updates the resolution:

| Feedback | Action | Effectiveness Change |
|----------|--------|---------------------|
| **Helpful** | `verified: true` | +0.10 (cap 1.0) |
| **Not Helpful** | `verified: false` | -0.20 (floor 0.3) |

### Why This Matters

When a new similar ticket arrives, the RAG pipeline retrieves past resolutions sorted by effectiveness. **Verified resolutions float to the top**, unverified ones sink. Over time, the system learns which fixes actually work.

```
New ticket → RAG retrieves similar tickets → Picks resolution with highest effectiveness
                                                        ↑
                                              Verified = 0.95 ← preferred
                                              Unverified = 0.60 ← deprioritized
```

### API

- Feedback submitted via `POST /api/tickets/{id}/feedback`
- Resolution quality updated automatically — no manual intervention needed

---

## Loop 2: Human Correction Learning (ATR-119)

**What it does:** When a human overrides the AI's classification, the system records exactly what went wrong and which classifiers failed — then uses that data to improve.

### How It Works

1. AI classifies ticket as "Infrastructure" with 73% confidence
2. Analyst reviews and overrides to "Database" with reason: "This is about PostgreSQL replication"
3. System records a **correction** with:
   - Original vs corrected category
   - Which classifiers were wrong (e.g., LLM + Centroid got it wrong)
   - Which classifiers were right (e.g., KNN already predicted "Database")
   - Quality gate: only trusted corrections from admin/engineer with substantive reason

### Immediate Improvement (KNN)

The KNN classifier uses live database tickets for voting. When a ticket's category is corrected:

```
Before override:
  KNN searches → finds this ticket labeled "Infrastructure" → votes "Infrastructure"

After override:
  KNN searches → finds this ticket labeled "Database" → votes "Database" ✓
```

**KNN improves immediately** — no retraining needed.

### Batch Improvement (Centroid)

The Centroid classifier compares embeddings to pre-computed category averages. When corrections accumulate:

```
Admin calls POST /api/corrections/recompute-centroids
  → Reads ALL tickets (with corrected categories)
  → Recomputes average embedding per category
  → Centroid classifier now reflects corrections
```

### Classifier Error Tracking

Every correction tracks which classifiers were wrong:

```json
{
  "original_category": "Infrastructure",
  "corrected_category": "Database",
  "classifiers_wrong": ["llm", "centroid"],
  "classifiers_right": ["knn"],
  "is_trusted": true
}
```

The `GET /api/corrections/stats` endpoint reveals patterns:

```json
{
  "classifier_errors": [
    {"classifier": "llm", "wrong_count": 12},
    {"classifier": "centroid", "wrong_count": 8},
    {"classifier": "keyword", "wrong_count": 15},
    {"classifier": "knn", "wrong_count": 3}
  ],
  "common_misclassifications": [
    {"from": "Infrastructure", "to": "Database", "count": 5},
    {"from": "Network", "to": "Security", "count": 3}
  ]
}
```

This tells the team: "KNN is our most accurate classifier. LLM keeps confusing Infrastructure with Database."

### Training Data Export

`GET /api/corrections/export` returns all trusted corrections in a format ready for evaluation:

```json
[
  {
    "title": "PostgreSQL replication lag growing",
    "description": "...",
    "original_category": "Infrastructure",
    "corrected_category": "Database",
    "classifier_votes": {...},
    "reason": "This is about DB replication, not server infrastructure"
  }
]
```

This data can be added to the evaluation set to measure accuracy improvements and tune classifier weights.

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/corrections/export` | Export corrections as training data |
| `POST /api/corrections/recompute-centroids` | Recompute centroids with corrected data |
| `GET /api/corrections/stats` | Correction analytics and classifier error rates |

---

## Loop 3: Repeated Issue Detection (ATR-120)

**What it does:** Detects when the same type of problem keeps generating tickets, so the team can fix the root cause.

### How It Works

1. System scans tickets from the last 7 days
2. Computes embedding similarity between all recent tickets
3. Groups tickets with >80% similarity into clusters
4. If a cluster has 3+ tickets → flagged as a **repeated issue**

### Example

```
Cluster detected: [5 tickets] "Redis OOM on prod-cache-01"
  - Ticket #1001: "Redis out of memory again" (May 12)
  - Ticket #1002: "Redis OOM killed by kernel" (May 13)
  - Ticket #1003: "Redis memory usage at 99%" (May 14)
  - Ticket #1004: "Application errors — Redis connection refused" (May 15)
  - Ticket #1005: "Redis cluster node failing" (May 16)

→ Root cause: Redis maxmemory too low. Fix: increase maxmemory or add eviction policy.
```

Instead of resolving 5 individual tickets, the team can fix the root cause once.

### API

| Endpoint | Purpose |
|----------|---------|
| `POST /api/corrections/detect-repeated-issues` | Run detection (admin) |
| `GET /api/corrections/repeated-issues` | Get flagged clusters |

---

## How All 3 Loops Work Together

```
Day 1: Ticket classified as "Infrastructure" (wrong — should be Database)
        │
        ├── Loop 2: Analyst overrides → correction logged
        │            → KNN immediately improves
        │            → Classifier error tracked (LLM was wrong)
        │
Day 2: Similar ticket arrives → KNN now votes "Database" correctly
        │            → System routes to Database Admin team
        │
Day 3: Engineer resolves ticket using AI suggestion
        │
        ├── Loop 1: User rates "helpful" → resolution verified
        │            → Next similar ticket gets this proven resolution
        │
Day 7: Admin runs detection
        │
        ├── Loop 3: Finds 5 similar DB replication tickets this week
        │            → Flags as repeated issue
        │            → Team investigates root cause
        │
Day 8: Admin recomputes centroids
        │
        ├── Loop 2: Centroid classifier now reflects all corrections
                     → Future classifications more accurate
```

---

## What Improves Automatically vs Manually

| Component | Auto-Improve | Manual Trigger | Doesn't Improve |
|-----------|-------------|----------------|-----------------|
| **KNN Classifier** | Immediately on override | — | — |
| **Centroid Classifier** | — | `POST /recompute-centroids` | — |
| **Resolution Suggestions** | On "helpful" feedback | — | — |
| **Repeated Issue Detection** | — | `POST /detect-repeated-issues` | — |
| **LLM Classifier** | — | — | External model (Ollama) |
| **Keyword Classifier** | — | — | Fixed patterns |

---

## Quality Gates

Not every correction is trusted. DeskMind uses quality gates to prevent bad data from entering the feedback loop:

### Correction Quality Gate
- Corrector must be **admin or engineer** (not regular user)
- Reason must be **at least 5 characters** (prevents "ok" or "." as justification)
- Corrections that pass → `is_trusted: true` → used for centroid recompute and training export
- Corrections that fail → stored for audit but NOT used for model improvement

### Resolution Quality Gate
- New resolutions start as `verified: false`
- Only "helpful" feedback promotes to `verified: true`
- "Not helpful" feedback lowers effectiveness score
- RAG naturally prefers verified resolutions (higher effectiveness = higher rank)

---

## Metrics and Monitoring

### Correction Stats (`GET /api/corrections/stats`)

```json
{
  "total_corrections": 47,
  "trusted_corrections": 42,
  "override_rate": 0.063,
  "by_original_category": [
    {"category": "Infrastructure", "count": 15},
    {"category": "Network", "count": 10}
  ],
  "classifier_errors": [
    {"classifier": "keyword", "wrong_count": 35},
    {"classifier": "llm", "wrong_count": 12},
    {"classifier": "centroid", "wrong_count": 18},
    {"classifier": "knn", "wrong_count": 5}
  ],
  "common_misclassifications": [
    {"from": "Infrastructure", "to": "Database", "count": 8},
    {"from": "Network", "to": "Security", "count": 5}
  ]
}
```

### Key Metrics to Watch

| Metric | Good | Concerning |
|--------|------|-----------|
| Override rate | < 10% | > 20% |
| KNN error rate | < 5% | > 15% |
| Repeated issues | 0-2 clusters/week | > 5 clusters/week |
| Resolution verification rate | > 70% helpful | < 50% helpful |

---

## Summary

DeskMind's self-learning system turns every human interaction into a training signal:

1. **Corrections improve KNN immediately** — the most impactful classifier gets better with every override
2. **Feedback gates resolution quality** — only proven fixes get recommended to future users
3. **Pattern detection prevents ticket floods** — recurring issues get flagged for root cause analysis
4. **Centroid recomputation captures drift** — category boundaries shift as corrections accumulate
5. **Training data export enables offline improvement** — corrections feed back into the evaluation pipeline

The system gets **smarter the more people use it** — without any model retraining or manual data labeling.
