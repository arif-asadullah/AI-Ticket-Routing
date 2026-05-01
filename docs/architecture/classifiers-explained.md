# How the 4 Classifiers Work — Technical Deep Dive

This document explains how each of DeskMind's 4 classifiers works internally, with math, logic, and real examples. Written so any developer or reviewer can understand the AI pipeline.

---

## Overview

DeskMind uses **4 independent classifiers** that vote on each ticket. No single classifier is trusted alone.

| # | Classifier | Weight | Method | Accuracy | Speed |
|---|-----------|--------|--------|----------|-------|
| 1 | LLM (Qwen 2.5:3B) | 0.40 | Reads ticket + context, reasons about root cause | ~85% | ~2-5s |
| 2 | KNN (K-Nearest Neighbors) | 0.30 | Top 5 similar tickets vote by category | ~80% | ~10ms |
| 3 | Centroid Distance | 0.20 | Compares to 6 category center points | ~75% | ~2ms |
| 4 | Keyword Rules | 0.10 | Counts keyword matches per category | ~55% | ~1ms |

They run independently, then the **Aggregator** combines their votes with weighted scoring, agreement bonuses, and confidence calibration.

---

## Classifier 1: LLM (weight: 0.40)

**File**: `backend/services/llm_classifier.py`

### How it works

The LLM (Qwen 2.5:3B running locally on Ollama) reads the ticket text plus all the context gathered from the knowledge graph, and reasons about the root cause.

### The prompt

The system prompt instructs the LLM to:
1. **Classify by ROOT CAUSE, not symptom** — "502 errors because PostgreSQL is down" = Database, not Application
2. Pick one of 6 categories with clear boundaries
3. Return structured JSON: `{category, priority, confidence, reasoning}`

The user prompt includes:
- The ticket title and description
- Infrastructure context from graph traversal (server type, team, services, experts)
- Similar past tickets with their categories and resolutions
- Error-matched past tickets

### Why it's the strongest

- Understands natural language
- Can reason about cause vs symptom
- Uses graph context that other classifiers can't read

### Why it's not the only one

- Small models (3B params) can hallucinate — confidently give wrong answers
- Slow (~2-5 seconds per ticket)
- If Ollama goes down, this classifier is unavailable

### Output

```json
{
  "category": "Access Management",
  "priority": "high",
  "confidence": 0.94,
  "reasoning": "LDAP account lockout is an identity/access management issue..."
}
```

---

## Classifier 2: KNN — K-Nearest Neighbors (weight: 0.30)

**File**: `backend/services/knn_classifier.py`

### The concept

When a new ticket arrives, find the **5 most similar past tickets** and see what category they were. Whatever category most of them have — that's the answer. Like asking 5 neighbors and going with the majority.

### Step by step

#### Step 1: Embedding

MiniLM converts the ticket description into 384 numbers (a vector):

```
"LDAP account locked after password rotation"
    ↓ MiniLM
[0.23, -0.15, 0.87, 0.03, ..., -0.42]   ← 384 numbers
```

These numbers capture the **meaning** of the text. Similar meanings → similar numbers.

#### Step 2: Find K=5 nearest neighbors

Compare the new ticket's embedding against all 855 stored tickets using **cosine similarity**:

```
                    A · B
cos(θ) = ─────────────────
           ||A|| × ||B||

Where:
  A · B    = a₁×b₁ + a₂×b₂ + ... + a₃₈₄×b₃₈₄    (dot product)
  ||A||    = √(a₁² + a₂² + ... + a₃₈₄²)           (magnitude of A)
  ||B||    = √(b₁² + b₂² + ... + b₃₈₄²)           (magnitude of B)

Result: 0.0 (completely different) to 1.0 (identical meaning)
```

ArangoDB's vector index does this comparison in ~20ms and returns the top 5.

#### Step 3: Weighted voting

Each neighbor votes for its category, weighted by how similar it is:

```
Top 5 neighbors:
  #1  "AD account lockout after policy change"    → Access Management (0.94)
  #2  "LDAP bind failing for service accounts"    → Access Management (0.91)
  #3  "SSO token not refreshing properly"         → Access Management (0.88)
  #4  "MFA enrollment broken for new users"       → Access Management (0.85)
  #5  "Brute force attack on login page"          → Security          (0.79)

Weighted scores:
  Access Management = 0.94 + 0.91 + 0.88 + 0.85 = 3.58
  Security          = 0.79                         = 0.79

Winner: Access Management
```

**The math:**

```
score(category_c) = Σ similarity_i    for all neighbors i where category_i = c
winner = argmax(score(c))
```

#### Step 4: Confidence

What fraction of neighbors agree with the winner:

```
confidence = count of neighbors voting for winner / K
           = 4 / 5
           = 0.80
```

### Output

```json
{
  "category": "Access Management",
  "confidence": 0.80,
  "vote_counts": {"Access Management": 4, "Security": 1},
  "neighbors": [... top 5 tickets ...]
}
```

### Strengths and weaknesses

| Strength | Weakness |
|----------|----------|
| No training needed — just store past tickets | Cold start — with 0 past tickets, can't classify |
| Improves automatically as tickets are resolved | Doesn't understand root cause vs symptom |
| Catches LLM hallucinations | Sensitive to miscategorized past tickets |
| Explainable — "these 5 tickets were similar" | Matches by wording, not reasoning |

---

## Classifier 3: Centroid Distance (weight: 0.20)

**File**: `backend/services/centroid_classifier.py`

### The concept

Each of the 6 categories has a **center point** (centroid) — the average embedding of all tickets in that category. A new ticket goes to whichever center it's closest to. Like checking which city center you're nearest to.

### How centroids are created (one-time, during seeding)

#### Step 1: Group all tickets by category

```
Infrastructure tickets (177):    [emb₁, emb₂, ..., emb₁₇₇]
Application tickets (162):       [emb₁, emb₂, ..., emb₁₆₂]
Database tickets (133):          [emb₁, emb₂, ..., emb₁₃₃]
Network tickets (139):           [emb₁, emb₂, ..., emb₁₃₉]
Security tickets (141):          [emb₁, emb₂, ..., emb₁₄₁]
Access Management tickets (103): [emb₁, emb₂, ..., emb₁₀₃]
```

#### Step 2: Average all embeddings per category

For each of the 384 dimensions:

```
                      1    N
centroid_c[d]  =  ─────  Σ  embedding_i[d]
                    N   i=1

Where:
  c = category (e.g., "Database")
  d = dimension (0 to 383)
  N = number of tickets in category c
```

Result: 6 centroid vectors, each 384 numbers long, stored in `category_centroids` collection.

```
Infrastructure centroid:    [0.12, -0.08, 0.45, ...]  ← "average infrastructure ticket"
Application centroid:       [0.34, 0.15, -0.22, ...]  ← "average application ticket"
Database centroid:          [0.56, -0.33, 0.67, ...]  ← "average database ticket"
Network centroid:           [-0.18, 0.44, 0.12, ...]  ← "average network ticket"
Security centroid:          [0.08, 0.29, -0.41, ...]  ← "average security ticket"
Access Management centroid: [0.41, -0.12, 0.33, ...]  ← "average access mgmt ticket"
```

### How classification works (every new ticket)

#### Step 1: Embed the new ticket

```
"LDAP account locked after password rotation"
    ↓ MiniLM
new_embedding = [0.39, -0.14, 0.35, ...]
```

#### Step 2: Cosine similarity to each centroid

Same formula as KNN, but only 6 comparisons instead of 855:

```
sim(new, Infrastructure)    = 0.58
sim(new, Application)       = 0.61
sim(new, Database)          = 0.55
sim(new, Network)           = 0.48
sim(new, Security)          = 0.63
sim(new, Access Management) = 0.92  ← CLOSEST
```

#### Step 3: Winner = highest similarity

```
Winner: Access Management (0.92)
```

#### Step 4: Gap-based confidence

The confidence comes from **how much closer** the winner is compared to the runner-up:

```
#1  Access Management: 0.92
#2  Security:          0.63

gap = 0.92 - 0.63 = 0.29
```

**The confidence formula:**

```
confidence = min(0.5 + gap × 5, 0.99)

confidence = min(0.5 + 0.29 × 5, 0.99)
           = min(1.95, 0.99)
           = 0.99   ← capped at 0.99
```

Why this formula:
- `0.5` = baseline (50%)
- `gap × 5` = amplifies the distance. Gap of 0.10 → +0.50, gap of 0.05 → +0.25
- `0.99` cap = never say 100% confident

**Ambiguous example** (small gap):

```
Access Management: 0.78
Application:       0.75

gap = 0.03

confidence = min(0.5 + 0.03 × 5, 0.99)
           = min(0.65, 0.99)
           = 0.65   ← LOW confidence (uncertain)
```

### Output

```json
{
  "category": "Access Management",
  "confidence": 0.99,
  "distances": {
    "Access Management": 0.92,
    "Security": 0.63,
    "Application": 0.61,
    "Infrastructure": 0.58,
    "Database": 0.55,
    "Network": 0.48
  }
}
```

### KNN vs Centroid — key difference

```
KNN:       "Which 5 INDIVIDUAL past tickets are most similar?"
           Compares to 855 tickets → 5 nearest → they vote

Centroid:  "Which CATEGORY CENTER is this ticket closest to?"
           Compares to 6 centroids → picks closest
```

| Aspect | KNN | Centroid |
|--------|-----|---------|
| Compares to | 855 individual tickets | 6 category averages |
| Speed | ~10ms (vector index) | ~2ms (6 comparisons) |
| Good at | Finding specific similar incidents | Capturing the "general feel" of a category |
| Weakness | Influenced by outliers | Loses detail (edge cases averaged out) |
| Shines when | Past tickets exist for this exact issue | New type of issue, no exact match |

---

## Classifier 4: Keyword Rules (weight: 0.10)

**File**: `backend/services/keyword_classifier.py`

### The concept

The simplest classifier. Each category has 25+ keywords. Count which category has the most keyword matches. Like checking a dictionary.

### The keyword dictionary

```python
KEYWORD_DICT = {
    "Infrastructure": ["cpu", "memory", "ram", "disk", "server", "vm", "kubernetes", ...],
    "Application":    ["api", "http", "endpoint", "bug", "error", "timeout", "500", ...],
    "Database":       ["postgres", "postgresql", "redis", "sql", "query", "index", ...],
    "Network":        ["ssl", "vpn", "firewall", "dns", "tcp", "latency", "bgp", ...],
    "Security":       ["breach", "vulnerability", "malware", "phishing", "cve", "exploit", ...],
    "Access Management": ["ldap", "active directory", "sso", "saml", "oauth", "mfa", ...],
}
```

### How it works

#### Step 1: Lowercase the ticket text

```
"LDAP account locked after password rotation on prod-ldap-01"
→ "ldap account locked after password rotation on prod-ldap-01"
```

#### Step 2: Count keyword matches per category

```
Infrastructure: 0 matches
Application:    0 matches
Database:       0 matches
Network:        0 matches
Security:       0 matches
Access Management: 3 matches ("ldap", "password", "account locked")
```

#### Step 3: Winner = highest count

```
Winner: Access Management (3 matches)
```

#### Step 4: Confidence = winner's score / total matches

```
confidence = 3 / 3 = 1.0
```

**The math:**

```
score(category_c) = count of keywords in KEYWORD_DICT[c] that appear in text
winner = argmax(score(c))
confidence = score(winner) / Σ score(all categories)
```

### When keywords get it wrong

```
"502 errors because PostgreSQL connection pool exhausted on prod-app-01"

Database keywords:   2 (postgresql, connection pool)
Application keywords: 3 (502, error, app)

Winner: Application (wrong! Root cause is Database)
```

The keyword classifier votes Application because "502" and "error" are application keywords, even though the root cause is a database connection issue. But with only 0.10 weight, it gets outvoted by the other 3 classifiers.

### Output

```json
{
  "category": "Access Management",
  "confidence": 1.0,
  "scores": {
    "Access Management": 3,
    "Infrastructure": 0,
    "Application": 0,
    "Database": 0,
    "Network": 0,
    "Security": 0
  }
}
```

### Why it exists despite low accuracy (~55%)

| Reason | Explanation |
|--------|------------|
| **Emergency fallback** | When Ollama crashes AND database is empty, this is the ONLY classifier that works. It uses no AI model and no database. |
| **Never crashes** | Pure string matching. No network calls, no dependencies, no exceptions. |
| **Instant** | Sub-millisecond. Adds zero latency to the pipeline. |
| **Baseline signal** | Even at 55%, it provides a weak signal that helps the aggregator. |

---

## How the Aggregator Combines All 4 Votes

**File**: `backend/services/aggregator.py`

### The 7-step process

#### Step 0: Select weights based on which classifiers are available

```
All 4 active: {llm: 0.40, knn: 0.30, centroid: 0.20, keyword: 0.10}
No LLM:       {knn: 0.45, centroid: 0.35, keyword: 0.20}
No data:      {llm: 0.80, keyword: 0.20}
Emergency:    {keyword: 1.00}
```

#### Step 1: Weighted category scores

For each category, sum (weight × confidence) across all classifiers voting for it:

```
Example votes:
  LLM:      Access Management (0.94)
  KNN:      Access Management (0.80)
  Centroid: Access Management (0.99)
  Keyword:  Application       (0.60)

Access Management = (0.40 × 0.94) + (0.30 × 0.80) + (0.20 × 0.99)
                  = 0.376 + 0.240 + 0.198
                  = 0.814

Application       = (0.10 × 0.60)
                  = 0.060

Winner: Access Management (0.814)
```

#### Step 2: Agreement bonus/penalty

```
4/4 agree: +0.05 (unanimous)
3/4 agree:  0.00 (near-unanimous)
2/4 agree: -0.05 (split vote)
1/4 agree: -0.10 (lone dissenter wins only on weight)
```

In this example: 3/4 agree → bonus = 0.00

#### Step 3: Contextual bonuses

```
Error code confirms category?  → +0.03
  (e.g., ERR-AD-001 service is active-directory, maps to Access Management → match!)

Graph context confirms?        → +0.02
  (e.g., managed_by team domain is "Access Management" → match!)
```

#### Step 4: Raw confidence

```
raw = 0.814 + 0.00 + 0.03 + 0.02 = 0.864
```

#### Step 5: Calibration

Dampens overconfidence based on agreement level:

```
4/4 agree AND raw ≥ 0.90: calibrated = raw × 0.98
3/4 agree AND raw ≥ 0.70: calibrated = raw × 0.95
2/4 agree:                 calibrated = raw × 0.80
1/4 agree:                 calibrated = raw × 0.75

In this example: 3/4 agree, raw = 0.864 ≥ 0.70
  calibrated = 0.864 × 0.95 = 0.821
```

#### Step 6: Quality cap

The input quality score (from Stage 1) sets a maximum:

```
HIGH quality (long text + entities + errors): cap = 0.99
MEDIUM quality (long text, no entities):      cap = 0.85
LOW quality (short text, no info):            cap = 0.75

final = min(calibrated, cap)
      = min(0.821, 0.99)
      = 0.821
```

#### Step 7: Route or escalate

```
confidence ≥ 0.70 → status = "routed" (auto-sent to team)
confidence < 0.70 → status = "escalated" (human reviews)

0.821 ≥ 0.70 → ROUTED to Access Management team
```

---

## Why 4 Classifiers Instead of 1?

```
Single LLM:          ~85% accuracy. Wrong 15% of the time. No fallback.
4-classifier ensemble: ~90%+ accuracy. Each catches the others' mistakes.
```

| Scenario | LLM says | KNN says | Centroid says | Keyword says | Ensemble result |
|----------|----------|---------|--------------|-------------|----------------|
| Clear case | Database | Database | Database | Database | Database (high confidence) |
| LLM hallucination | Security | Access Mgmt | Access Mgmt | Access Mgmt | Access Mgmt (LLM overruled) |
| Ambiguous ticket | Application | Database | Application | Application | Application (escalated — low agreement) |
| Ollama down | (skipped) | Database | Database | Application | Database (degraded but working) |
| Everything down | (skipped) | (skipped) | (skipped) | Network | Network (escalated — low confidence) |
