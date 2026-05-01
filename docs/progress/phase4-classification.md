# Phase 4: 4-Classifier Ensemble Pipeline

## What We Did

Built the complete AI classification pipeline that takes a ticket and routes it to the correct team. This is the **brain of DeskMind** — the most important part.

Instead of using one AI model (which can be wrong ~20% of the time), we built **4 independent classifiers that vote**. When 3 out of 4 agree, we're confident. When they disagree, we escalate to a human.

## The 5 Stages

```
Ticket submitted → Stage 1 (Prepare) → Stage 2 (Retrieve) → Stage 3 (Classify) → Stage 4 (Aggregate) → Stage 5 (Route)
```

---

## Stage 1: Prepare

Three services scan the raw ticket text to extract useful signals before any AI runs.

### 1.1 Entity Extractor

**File**: `backend/services/entity_extractor.py`

**What it does**: Scans the ticket description for known server names, service names, and error patterns.

**How it works**:
1. On first call, loads all server keys (15), service keys/names (12), and error patterns (20) from ArangoDB
2. Caches them in memory for 5 minutes (no DB query per ticket)
3. For each ticket: case-insensitive string search against the cached lists

**Example**:
```
Input:  "prod-db-01 refusing connections. FATAL: too many connections"
Output: {
    servers: ["prod-db-01"],
    services: ["postgresql"],
    error_codes: [{ error_key: "ERR-PG-001", pattern: "FATAL: too many connections", service: "postgresql", severity: "high" }]
}
```

**Why it matters**:
- The extracted server name feeds into Graph Traversal (Stage 2) — so the system can follow edges from prod-db-01 to find who manages it, what services run on it, and past tickets on this server.
- The error code feeds into Error Matching (Stage 2) — finds past tickets with the same error.
- Both feed into Quality Scorer — having entities means higher quality score.

**Database fields it reads**: `servers._key`, `services._key`, `services.name`, `error_codes.pattern`

---

### 1.2 Error Scanner

**File**: `backend/services/error_scanner.py`

**What it does**: A thin wrapper around Entity Extractor focused on error code logic.

**Extra features beyond Entity Extractor**:
- `get_highest_severity(errors)` — returns the worst severity among matched errors (critical > high > medium > low)
- `errors_confirm_category(errors, category)` — checks if the matched error codes belong to the same category the AI classified. Used by the Aggregator for a confidence bonus.

**Example**:
```
Matched error: ERR-PG-001 (service: postgresql)
AI classified as: "Database"
errors_confirm_category? → YES (postgresql = Database) → +0.03 confidence bonus
```

**Service-to-category mapping**:
```
postgresql, redis → Database
nginx, order-service → Application
kubernetes, linux → Infrastructure
firewall, vpn, dns → Network
active-directory → Access Management
nfs → Infrastructure
```

---

### 1.3 Quality Scorer

**File**: `backend/services/quality_scorer.py`

**What it does**: Assesses how detailed the ticket text is. Determines the maximum confidence the system is allowed to have.

**Scoring rules**:
| Score | When | Max confidence |
|-------|------|---------------|
| **HIGH** | Description > 50 chars AND has server/service name or error code | 0.99 |
| **MEDIUM** | Description > 50 chars but no recognizable entities | 0.85 |
| **LOW** | Description < 50 chars, no entities, no errors | 0.75 |

**Why it matters**: Prevents the AI from being overconfident on vague tickets. If someone submits "server down help" (11 chars, no entities), the system caps confidence at 0.75 — which likely triggers escalation to a human instead of auto-routing to the wrong team.

**Example**:
```
"prod-db-01 refusing connections. FATAL: too many connections" → HIGH (long + has entity + has error)
"The checkout page is slow for customers"                       → MEDIUM (long but no entities)
"help broken"                                                   → LOW (short, no info)
```

---

## Stage 2: Retrieve

**File**: `backend/services/retrieval.py`

Four search methods run to gather context from the database. Each method finds different types of useful information.

### 2.1 Vector Similarity Search

**What it does**: Finds the 5 past tickets most similar in **meaning** to the new ticket.

**How**:
1. The new ticket's description is already converted to a 384-number embedding (in Stage 1)
2. ArangoDB compares this embedding to all 855 ticket embeddings using cosine similarity
3. Returns top 5 matches with their categories, resolutions, and similarity scores

**What it finds**: Past tickets with similar meaning, even if they use different words.

**Example**: "PostgreSQL not accepting connections" finds "Database connection pool exhausted" (84% similar) — different words, same problem.

**Database fields used**: `tickets.embedding` (via vector index), `tickets.category`, `resolutions.steps` (via `resolved_with` edge)

### 2.2 Error Code Match

**What it does**: Finds past tickets that had the **exact same error code**.

**How**:
1. From Stage 1, we know the ticket matches ERR-PG-001
2. Follow `triggered_by` edges from `error_codes/ERR-PG-001` to all past tickets
3. Get their resolutions

**What it finds**: Historical fixes for this specific error — very targeted.

**Database fields used**: `error_codes._key`, `triggered_by` edges, `tickets.category`, `resolutions.steps`

### 2.3 Graph Traversal

**What it does**: Follows connections from the mentioned server/service to find infrastructure context.

**How**:
1. From Stage 1, we know the ticket mentions "prod-db-01"
2. Start at `servers/prod-db-01` and follow edges:
   - `hosts` → what services run on it (PostgreSQL, Redis)
   - `managed_by` → which team manages it (Database Admin)
   - `affects` (reversed) → past tickets on this server (5 found)
   - `member_of` (reversed from team) → experts on the team (Arjun Nair, Meera Patel)
3. Also follows `depends_on` to find what breaks if this service is down

**What it finds**: Who manages the server, what past issues it had, who has the expertise to fix it.

**Database fields used**: `servers.type`, `servers.datacenter`, `teams.name`, `teams.domain`, `engineers.name`, `engineers.expertise` + all edge collections

### 2.4 Full-text Keyword Search

**What it does**: Finds past tickets with matching keywords.

**How**: Takes the top 5 significant words from the ticket and searches using ArangoDB's fulltext index on `tickets.description`.

**What it finds**: Past tickets that mention the same terms — complements vector search.

---

## Stage 3: Classify (4 Independent Classifiers)

Each classifier looks at the ticket independently and votes. They don't see each other's output.

### 3.1 LLM Classifier (Classifier 1, weight: 0.40)

**File**: `backend/services/llm_classifier.py`

**What it does**: Sends the ticket + all Stage 2 context to Qwen 2.5:3B via Ollama. The model reads everything and returns a classification.

**The prompt includes**:
1. **Root-cause instruction**: "Classify by ROOT CAUSE, not symptom. '502 errors because PostgreSQL is down' = Database, not Application."
2. **Category definitions**: Clear boundaries for all 6 categories
3. **Infrastructure context** from graph traversal (server type, team, services)
4. **Similar past tickets** with their categories and resolutions
5. **Error-matched tickets** from the same error code

**Output**: `{category: "Database", priority: "high", confidence: 0.94, reasoning: "PostgreSQL connection issue..."}`

**Why it's the strongest**: It understands natural language, can reason about root cause vs symptom, and uses context from similar past tickets.

**Why it's not the only one**: Small models (3B params) can hallucinate — confidently give wrong answers. The other 3 classifiers catch these mistakes.

**How it connects to Ollama**: Calls `http://host.docker.internal:11434/v1/chat/completions` (OpenAI-compatible API). Model: `qwen2.5:3b`. Timeout: 120 seconds.

---

### 3.2 KNN Classifier (Classifier 2, weight: 0.30)

**File**: `backend/services/knn_classifier.py`

**What it does**: Takes the 5 most similar tickets from vector search and lets them **vote**.

**How it works**:
1. Get top 5 similar tickets (already found in Stage 2)
2. Count how many are in each category (weighted by similarity score)
3. Majority wins

**Example**:
```
5 nearest neighbors:
  1. "PostgreSQL max_connections reached"     → Database (0.88)
  2. "Database Connection Timeout"            → Database (0.82)
  3. "PostgreSQL Connection Pool Exhaustion"  → Database (0.74)
  4. "Database Write Operation Timeout"       → Database (0.74)
  5. "Database Connection Pool Exhausted"     → Database (0.72)

Vote: Database wins (5/5 = 100% agreement)
Confidence: 1.0
```

**Why it helps**: It's a completely independent signal. If the LLM hallucinates "Security" but 4/5 neighbors say "Database", the KNN corrects it.

**No AI model needed**: Pure math on pre-computed similarities. Instant.

---

### 3.3 Centroid Classifier (Classifier 3, weight: 0.20)

**File**: `backend/services/centroid_classifier.py`

**What it does**: Compares the ticket's embedding to the **average embedding** of each category.

**How it works**:
1. Load 6 centroids from `category_centroids` collection (cached in memory for 1 hour)
2. Compute cosine similarity between the new ticket's embedding and each centroid
3. Closest centroid = predicted category
4. Confidence = how much closer to the winner vs second best

**Example**:
```
Distances (similarity scores):
  Database:       0.75  ← CLOSEST
  Application:    0.64
  Infrastructure: 0.64
  Network:        0.60
  Security:       0.54
  Access Management: 0.45

Winner: Database (confidence: 0.99)
```

**Why it helps**: Even when no single past ticket is very similar, the centroid captures the **general feel** of what Database tickets look like. Robust against outliers.

**No AI model needed**: Pure vector math. Instant.

---

### 3.4 Keyword Classifier (Classifier 4, weight: 0.10)

**File**: `backend/services/keyword_classifier.py`

**What it does**: Counts keyword matches per category from hardcoded dictionaries.

**How it works**:
1. Each category has 25+ keywords: Database (postgres, redis, sql, query, index...), Network (firewall, vpn, dns, ssl...), etc.
2. Scan the ticket text for each keyword
3. Category with most matches wins

**Example**:
```
"prod-db-01 refusing connections. FATAL: too many connections. App 502 errors."

Database keywords matched:    0  (no direct DB keywords in this text!)
Application keywords matched: 2  (502, error)
Infrastructure keywords matched: 0

Winner: Application (wrong! But that's ok — it only has 10% weight)
```

**Why it's the weakest (~55%)**: It doesn't understand meaning. "502 errors" contains Application keywords even though the root cause is Database.

**Why we still use it**: It's the **emergency fallback** when everything else is down (Ollama crashed + database empty). Works without any AI or database. Never crashes.

---

## Stage 4: Aggregate

**File**: `backend/services/aggregator.py`

**What it does**: Combines all 4 classifier votes into one final decision using weighted voting.

### How it works:

**Step 1 — Weighted scores**:
```
For each category, sum (weight × confidence) across classifiers:

Database:
  LLM:      0.40 × 1.00 = 0.400
  KNN:      0.30 × 1.00 = 0.300
  Centroid: 0.20 × 0.99 = 0.198
  Keyword:  0.10 × 0.00 = 0.000  (keyword voted Application)
  Total:                   0.898

Application:
  Keyword:  0.10 × 1.00 = 0.100
  Total:                   0.100

Winner: Database (0.898)
```

**Step 2 — Agreement bonus/penalty**:
```
3 out of 4 agree on Database:
  Agreement: 3/4 → no bonus (0.00)
  If 4/4 agreed: +0.05
  If only 2/4: -0.05
  If 1/4: -0.10
```

**Step 3 — Contextual bonuses**:
```
Error code ERR-PG-001 confirms Database? → YES → +0.03
Graph says server managed by Database team? → YES → +0.02
```

**Step 4 — Calibration**:
```
Raw: 0.898 + 0.00 + 0.03 + 0.02 = 0.948
3/4 agree and raw ≥ 0.70 → multiply by 0.95
Calibrated: 0.948 × 0.95 = 0.901
```

**Step 5 — Quality cap**:
```
Quality score: HIGH → max 0.99
Final: min(0.901, 0.99) = 0.901
```

**Step 6 — Secondary category**:
```
Runner-up: Application (0.100)
0.100 < 0.15 → no secondary category (clearly Database)
```

**Final result**: Database, 90.1% confidence, 3/4 agreement

### Degradation weights:

When classifiers are unavailable, weights automatically redistribute:

| Level | Available | Weights |
|-------|-----------|---------|
| Full (Level 4) | LLM + KNN + Centroid + Keywords | 0.40, 0.30, 0.20, 0.10 |
| No data (Level 3) | LLM + Keywords | 0.80, 0.20 |
| No LLM (Level 2) | KNN + Centroid + Keywords | 0.45, 0.35, 0.20 |
| Emergency (Level 1) | Keywords only | 1.00 |

---

## Stage 5: Orchestrate + Route

**File**: `backend/services/orchestrator.py`

**What it does**: The master controller that ties everything together into **one function call**.

### What `classify()` does:

```python
result = await classify(title, description, db, redis_client)
```

1. **Health check** — checks if Ollama is running, if DB has data, if Redis is available. Cached for 5 seconds.
2. **Determine degradation level** (1-4) based on health
3. **Stage 1** — extract entities, score quality, compute embedding
4. **Stage 2** — run 4 retrieval methods (skip if no data)
5. **Stage 3** — run active classifiers based on degradation level
6. **Stage 4** — aggregate votes
7. **Enrich** — look up team name, find suggested resolution, recommend expert
8. **Return** everything: category, confidence, classifier_votes, team, expert, processing time

### Embedding model:

Loaded once as a singleton. `SentenceTransformer("all-MiniLM-L6-v2")` — takes ~2 seconds on first call, cached after that.

### Health check:

```python
async def check_health():
    ollama_ok = ping http://host.docker.internal:11434 (timeout 2s)
    db_has_data = tickets.count() > 0
    redis_ok = redis.ping()

    if ollama_ok and db_has_data: level = 4 (Full)
    if ollama_ok and not db_has_data: level = 3 (No data)
    if not ollama_ok and db_has_data: level = 2 (No LLM)
    else: level = 1 (Emergency)
```

---

## API Integration

**File**: `backend/api/tickets.py`

### What happens when a user submits a ticket via the frontend:

1. **Frontend** sends `POST /api/tickets` with title + description
2. **API** calls `await classify(title, description, db, redis)`
3. **Orchestrator** runs the full 5-stage pipeline (~10 seconds)
4. **API** determines status:
   - confidence ≥ 0.70 → `status: "routed"` (auto-sent to team)
   - confidence < 0.70 → `status: "escalated"` (human reviews)
5. **API** saves ticket to database with:
   - All classification fields (category, confidence, reasoning, classifier_votes)
   - The 384-dim embedding (for future KNN/centroid improvements)
   - `_source: "user"` tag (to distinguish from seed/synthetic data)
6. **API** creates edges:
   - `assigned_to` (ticket → team)
7. **API** writes to `audit_log`:
   - What the AI decided, confidence, all 4 classifier signals
8. **API** returns full result to frontend

### List tickets endpoint:

`GET /api/tickets` now filters out seed/synthetic data — only shows user-submitted tickets.

---

## Test Results

Tested with: "PostgreSQL not accepting connections on prod-db-01"

```
Category:    Database
Confidence:  90.1%
Agreement:   3/4
Status:      routed
Team:        Database Admin
Expert:      Meera Patel

Classifier votes:
  LLM:      Database (100%)
  KNN:      Database (100%) — 5/5 neighbors agree
  Centroid: Database (99%)
  Keyword:  Application (100%) — wrong, but overruled by other 3
```

The keyword classifier was wrong (it saw "502" → Application), but the ensemble correctly chose Database with 90.1% confidence.

---

## File Summary

| File | What it does | Stage |
|------|-------------|-------|
| `backend/services/entity_extractor.py` | Extract server/service names from text | Stage 1 |
| `backend/services/error_scanner.py` | Match known error patterns | Stage 1 |
| `backend/services/quality_scorer.py` | Assess input quality (HIGH/MEDIUM/LOW) | Stage 1 |
| `backend/services/retrieval.py` | 4 parallel searches (vector, error, graph, fulltext) | Stage 2 |
| `backend/services/llm_classifier.py` | Qwen 2.5:3B classification with context | Stage 3 |
| `backend/services/knn_classifier.py` | K-nearest neighbors voting | Stage 3 |
| `backend/services/centroid_classifier.py` | Category centroid distance | Stage 3 |
| `backend/services/keyword_classifier.py` | Keyword counting fallback | Stage 3 |
| `backend/services/aggregator.py` | Weighted voting + calibration | Stage 4 |
| `backend/services/orchestrator.py` | Master controller + health + degradation | Stage 5 |
| `backend/api/tickets.py` | API endpoint → orchestrator → DB → edges → audit | API |
