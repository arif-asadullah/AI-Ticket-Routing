# DeskMind Improved Classification Architecture

## Design Goals

1. **High accuracy** — target 90%+ on real-world IT tickets
2. **No single point of failure** — if one method fails, others compensate
3. **Calibrated confidence** — confidence score must be meaningful (0.90 should be right 90% of the time)
4. **Graceful degradation** — system works even when LLM is down or database is empty
5. **Explainable** — every classification can be traced back to why

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     NEW TICKET SUBMITTED                         │
│  "PostgreSQL not accepting connections on prod-db-01.            │
│   FATAL: too many connections. App team reporting 502 errors."   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   STAGE 1: PREPARE    │
                │   Pre-process text    │
                │   Extract signals     │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   STAGE 2: RETRIEVE   │
                │   4 parallel searches │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   STAGE 3: CLASSIFY   │
                │   4 independent       │
                │   classifiers vote    │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   STAGE 4: AGGREGATE  │
                │   Weighted voting +   │
                │   confidence calc     │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   STAGE 5: DECIDE     │
                │   Route or Escalate   │
                └───────────────────────┘
```

The key insight: **4 classifiers vote independently, then we aggregate**. This is called an **ensemble approach** — the same technique used in weather forecasting (multiple weather models, averaged) and medical diagnosis (multiple doctors, consensus).

---

## Stage 1: PREPARE (Pre-processing)

Before any classification happens, we extract all useful signals from the raw ticket text.

### Step 1.1: Text Normalization

Clean the ticket text so all classifiers work with consistent input:

```
Raw:    "HELP!! prod-db-01 is DOWN!!!! FATAL: too many connections\n\t
         plese help asap.. app team seeing 502s"

Normalized: "help prod-db-01 is down fatal too many connections
             please help asap app team seeing 502s"

Operations:
  - Lowercase
  - Remove excessive punctuation (!!!! → !)
  - Fix common typos (plese → please, envrionment → environment)
  - Normalize whitespace
  - Keep original text too (for LLM — it handles messy text well)
```

### Step 1.2: Entity Extraction

Scan text for known infrastructure names:

```
Input: "prod-db-01 is down, PostgreSQL FATAL error"

Extracted:
  servers:  ["prod-db-01"]    ← matched against servers._key
  services: ["postgresql"]    ← matched against services._key / services.name
  errors:   ["ERR-PG-001"]   ← matched "FATAL: too many connections" against error_codes.pattern

Not found:
  teams:    []                ← no team name mentioned
  engineers: []               ← no person mentioned
```

### Step 1.3: Quality Check

Assess ticket quality before proceeding:

```
Quality signals:
  description_length: 156 chars  ✅ (minimum: 20 chars)
  has_entities: true              ✅ (server or service mentioned)
  has_error_code: true            ✅ (known error pattern found)

Quality score: HIGH → proceed with all 4 classifiers

If quality = LOW (very short, no entities, no error):
  → Still classify, but cap maximum confidence at 0.75
  → Always add a flag: "low_quality_input: true"
```

### Output of Stage 1:

```json
{
  "original_text": "HELP!! prod-db-01 is DOWN!!!!...",
  "normalized_text": "help prod-db-01 is down...",
  "entities": {
    "servers": ["prod-db-01"],
    "services": ["postgresql"],
    "error_codes": ["ERR-PG-001"]
  },
  "quality_score": "HIGH",
  "embedding": [0.82, -0.15, 0.33, ...]
}
```

---

## Stage 2: RETRIEVE (4 Parallel Searches)

Four search methods run **simultaneously** to gather context:

```
                    Prepared ticket
                   /    |     |    \
                  /     |     |     \
                 ▼      ▼     ▼      ▼
            ┌───────┐┌──────┐┌──────┐┌──────────┐
            │Vector ││Error ││Graph ││Full-text │
            │Search ││Match ││Walk  ││Search    │
            └───┬───┘└──┬───┘└──┬───┘└────┬─────┘
                │       │       │         │
                ▼       ▼       ▼         ▼
            5 similar  Past   Infra     Keyword
            tickets   tickets context   matches
```

### Search 2.1: Vector Similarity Search

**Input**: ticket embedding (384 numbers)
**Searches**: `tickets.embedding` via vector index
**Returns**: Top 5 most similar past tickets with their categories and resolutions

```
Results:
  1. TKT-042 "PostgreSQL max_connections reached"       → Database (0.96 similarity)
  2. TKT-078 "Database connection pool exhausted"        → Database (0.89)
  3. TKT-056 "Slow queries blocking production"          → Database (0.72)
  4. TKT-033 "Redis OOM on prod-app-01"                  → Database (0.65)
  5. TKT-099 "NGINX 502 after deployment"                → Application (0.55)
```

### Search 2.2: Error Code Pattern Match

**Input**: matched error codes from Stage 1
**Searches**: `triggered_by` edges from error_codes to past tickets
**Returns**: Past tickets with the same error code

```
ERR-PG-001 → TKT-042 (Database), TKT-089 (Database), TKT-112 (Database)

All 3 past tickets with this error = Database
```

### Search 2.3: Graph Traversal

**Input**: extracted server/service entities
**Follows**: `hosts`, `managed_by`, `affects`, `depends_on`, `member_of` edges
**Returns**: Infrastructure context

```
From servers/prod-db-01:
  type: "database"
  services: [PostgreSQL, Redis]
  managed_by: teams/db-admin (domain: "Database")
  past_tickets: [TKT-042 (Database), TKT-056 (Database), TKT-078 (Database)]
  dependent_services: [OrderService, AuthService]
  experts: [Arjun Nair (PostgreSQL), Meera Patel (replication)]
```

### Search 2.4: Full-Text Keyword Search

**Input**: normalized ticket text
**Searches**: `tickets.title` and `tickets.description` via fulltext index
**Returns**: Past tickets with matching keywords

```
FULLTEXT search for "PostgreSQL connections":
  1. TKT-042 "PostgreSQL max_connections reached" → Database
  2. TKT-089 "PostgreSQL connection limit on prod-db-02" → Database
  3. TKT-026 "Redis connection pool exhausted" → Database
```

---

## Stage 3: CLASSIFY (4 Independent Classifiers)

This is the core of the improved architecture. Instead of one classifier, we use **4 independent classifiers**, each using a different method. They don't see each other's output.

```
┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ CLASSIFIER 1   │  │ CLASSIFIER 2   │  │ CLASSIFIER 3   │  │ CLASSIFIER 4   │
│ LLM + Context  │  │ KNN Voting     │  │ Centroid       │  │ Keyword Rules  │
│                │  │                │  │ Distance       │  │                │
│ Accuracy: ~85% │  │ Accuracy: ~80% │  │ Accuracy: ~75% │  │ Accuracy: ~55% │
│ Weight: 0.40   │  │ Weight: 0.30   │  │ Weight: 0.20   │  │ Weight: 0.10   │
└───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
        │                   │                   │                   │
        ▼                   ▼                   ▼                   ▼
    Database            Database            Database            Database
    (conf: 0.92)        (4/5 agree)         (dist: 0.12)        (score: 2)
```

### Classifier 1: LLM with Context (Weight: 0.40)

The strongest classifier. Phi-3-mini reads the ticket **plus all context gathered in Stage 2**.

**Why it's the strongest**: It understands natural language, can reason about root cause vs symptom, and uses context from similar past tickets.

**The prompt** (carefully designed):

```
SYSTEM:
You are DeskMind, an expert IT ticket classifier. Your job is to identify
the ROOT CAUSE domain, not the symptom.

RULES:
1. Classify by ROOT CAUSE, not by symptom.
   - "502 errors because PostgreSQL is down" = Database (not Application)
   - "VPN drops after firewall rule change" = Network (not Security)
   - "SSO login failing after LDAP config change" = Access Management (not Infrastructure)

2. Categories (pick exactly ONE):
   - Infrastructure: Server hardware, OS, CPU, RAM, VMs, Kubernetes nodes, Docker daemon
   - Application: App crashes, API errors, HTTP 5xx from app code, deployments, bugs
   - Database: SQL databases, Redis, connection pools, queries, replication, backups
   - Network: Firewalls, DNS, VPN, load balancers, latency, routing, certificates
   - Security: Authentication, authorization, vulnerabilities, malware, access control
   - Access Management: LDAP, Active Directory, SSO, SAML, OAuth, MFA, RBAC, permissions, account lockouts

3. Priority:
   - critical: Production completely down, data loss risk, security breach
   - high: Major feature broken, significant performance degradation
   - medium: Partial impact, workaround available
   - low: Minor issue, no immediate business impact

CONTEXT FROM KNOWLEDGE GRAPH:
Server: prod-db-01 (type: database, datacenter: ap-south-1, RAM: 32GB)
Services on this server: PostgreSQL 15.4, Redis 7.2
Managed by: Database Admin team
Error detected: ERR-PG-001 "FATAL: too many connections" (severity: high)
Dependent services: OrderService, AuthService (these will also be affected)

SIMILAR PAST TICKETS (from vector search):
1. [Database, high] "PostgreSQL max_connections reached"
   Resolution: Killed idle connections, increased max_connections → effectiveness: 0.95
2. [Database, high] "Database connection pool exhausted"
   Resolution: Increased pool size in app config → effectiveness: 0.85
3. [Database, high] "Slow queries blocking production traffic"
   Resolution: Added missing index → effectiveness: 0.95

PAST TICKETS WITH SAME ERROR (ERR-PG-001):
1. [Database, high] "PostgreSQL max_connections reached"
2. [Database, high] "PostgreSQL connection limit on prod-db-02"
3. [Database, high] "Database refusing connections after restart"

NOW CLASSIFY THIS NEW TICKET:
Title: "PostgreSQL not accepting connections on prod-db-01"
Description: "prod-db-01 refusing connections since 10am. max_connections reached
at 100. FATAL: too many connections in logs. App team reporting 502 errors."

Return ONLY valid JSON (no other text):
{
  "category": "one of: Infrastructure, Application, Security, Database, Access Management, Network",
  "priority": "one of: critical, high, medium, low",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentences explaining root cause analysis"
}
```

**Output**:
```json
{
  "category": "Database",
  "priority": "high",
  "confidence": 0.94,
  "reasoning": "PostgreSQL connection limit is a database configuration issue. The FATAL: too many connections error (ERR-PG-001) is a known database error. The 502 errors reported by the app team are a downstream symptom caused by the database being unable to accept new connections, not an application code issue."
}
```

### Classifier 2: KNN Voting (Weight: 0.30)

**K-Nearest Neighbors** — purely mathematical, no LLM involved.

Takes the top 5 similar tickets from vector search and **votes by their categories**:

```
5 nearest neighbors:
  1. TKT-042 → Database     (similarity: 0.96)
  2. TKT-078 → Database     (similarity: 0.89)
  3. TKT-056 → Database     (similarity: 0.72)
  4. TKT-033 → Database     (similarity: 0.65)
  5. TKT-099 → Application  (similarity: 0.55)

Vote count:
  Database: 4 votes
  Application: 1 vote

Weighted vote (by similarity):
  Database: 0.96 + 0.89 + 0.72 + 0.65 = 3.22
  Application: 0.55 = 0.55

Winner: Database
KNN confidence: 4/5 = 0.80 (80% of neighbors agree)
```

**Why this helps**: It's a completely independent signal. If the LLM hallucinates "Security" but 4/5 similar tickets are "Database", the KNN corrects the LLM.

**When it fails**: When the database has few tickets, or the new ticket is unlike anything seen before.

### Classifier 3: Category Centroid Distance (Weight: 0.20)

**Pre-computed**: For each category, we compute the **average embedding** (centroid) of all tickets in that category.

```
Category centroids (pre-computed once, updated periodically):
  Infrastructure centroid: [0.15, 0.42, -0.33, ...]   ← average of all Infrastructure ticket embeddings
  Application centroid:    [0.28, 0.11, -0.08, ...]
  Database centroid:       [0.77, -0.12, 0.29, ...]
  Network centroid:        [-0.05, 0.55, 0.18, ...]
  Security centroid:       [0.33, 0.08, -0.41, ...]
  Access Management centroid: [0.44, -0.27, 0.51, ...]
```

Compare the new ticket's embedding to each centroid:

```
New ticket embedding: [0.82, -0.15, 0.33, ...]

Distances:
  Database:       0.12  ← CLOSEST (most similar to Database tickets overall)
  Infrastructure: 0.45
  Access Management: 0.52
  Application:    0.61
  Network:        0.68
  Security:       0.74

Winner: Database
Centroid confidence: 1 - (0.12 / 0.74) = 0.84  (normalized distance ratio)
```

**Why this helps**: Even if no single past ticket is very similar, the centroid captures the **general pattern** of what Database tickets look like. It's robust against outliers.

**When it fails**: When a ticket is genuinely between two categories (the embedding sits exactly between two centroids).

### Classifier 4: Keyword Rule Engine (Weight: 0.10)

The simplest classifier — no AI, just keyword counting:

```
Keyword dictionaries:
  Infrastructure: cpu, memory, ram, disk, server, vm, container, kubernetes,
                  docker, deployment, restart, crash, oom, kernel, hardware
  Application:    api, http, endpoint, bug, error, exception, timeout,
                  response, frontend, backend, deploy, version, 500, 503
  Database:       postgres, mysql, oracle, redis, mongo, sql, query, index,
                  table, schema, migration, replica, connection pool, deadlock
  Network:        ssl, vpn, firewall, dns, tcp, udp, latency, packet,
                  route, subnet, bandwidth, proxy, load balancer, certificate
  Security:       authentication, authorization, rbac, token, encryption,
                  breach, vulnerability, malware, phishing, audit, permission
  Access Management: ldap, active directory, sso, saml, oauth, mfa, rbac, permission,
                  account lockout, group policy, kerberos, identity, provisioning, directory service

Scan: "PostgreSQL not accepting connections on prod-db-01.
       FATAL: too many connections. App team reporting 502."

Matches:
  Database:       postgres ✅, connections ✅, connection ✅  → score: 3
  Application:    502 ✅                                      → score: 1
  Infrastructure: (none)                                      → score: 0
  Network:        (none)                                      → score: 0
  Security:       (none)                                      → score: 0
  Access Management: (none)                                   → score: 0

Winner: Database (score 3)
```

**Why this helps**: It's the **fallback when everything else fails** (LLM down, database empty). It also catches obvious cases instantly. It's never wrong on easy tickets ("PostgreSQL backup failed" → obviously Database).

**When it fails**: Ambiguous tickets where keywords from multiple categories appear ("firewall blocking database port" has both Network and Database keywords).

---

## Stage 4: AGGREGATE (Weighted Voting + Confidence Calibration)

Now we combine all 4 classifiers' votes:

```
Classifier results:
  1. LLM + Context:     Database  (confidence: 0.94)  weight: 0.40
  2. KNN Voting:        Database  (4/5 agree = 0.80)  weight: 0.30
  3. Centroid Distance:  Database  (dist ratio = 0.84) weight: 0.20
  4. Keyword Rules:      Database  (score: 3/1 = 0.75) weight: 0.10
```

### Step 4.1: Weighted Category Vote

```
For each category, sum the weighted confidences:

Database:
  = (0.40 × 0.94) + (0.30 × 0.80) + (0.20 × 0.84) + (0.10 × 0.75)
  = 0.376 + 0.240 + 0.168 + 0.075
  = 0.859

Application:
  = (0.40 × 0.00) + (0.30 × 0.11) + (0.20 × 0.00) + (0.10 × 0.25)
  = 0.000 + 0.033 + 0.000 + 0.025
  = 0.058

(other categories ≈ 0)

Winner: Database (0.859)
Runner-up: Application (0.058)
```

### Step 4.2: Agreement Bonus/Penalty

```
All 4 classifiers agree on Database?
  YES → Agreement bonus: +0.05

Final score: 0.859 + 0.05 = 0.909

If classifiers disagreed (e.g., LLM says Network, KNN says Database):
  → Agreement penalty: -0.10
  → Forces escalation for ambiguous cases
```

### Step 4.3: Contextual Adjustments

```
Error code found (ERR-PG-001) and its service = postgresql = Database?
  YES → Error code bonus: +0.03

Graph says server type = "database" and managed_by domain = "Database"?
  YES → Graph bonus: +0.02

Adjusted confidence: 0.909 + 0.03 + 0.02 = 0.959
Cap at 0.99 (never 1.0 — always leave room for error)

Final confidence: 0.959
```

### Step 4.4: Confidence Calibration

Raw confidence numbers are often **overconfident**. We calibrate using a simple mapping learned from evaluation data:

```
If raw confidence ≥ 0.90 and all 4 agree → calibrated = raw × 0.98 (slight reduction)
If raw confidence ≥ 0.70 and 3/4 agree  → calibrated = raw × 0.95
If raw confidence ≥ 0.70 but only 2 agree → calibrated = raw × 0.80 (significant reduction)
If raw confidence < 0.70                  → calibrated = raw × 0.75

Our case: 0.959 × 0.98 = 0.940 (calibrated)
```

### Output of Stage 4:

```json
{
  "category": "Database",
  "priority": "high",
  "confidence": 0.940,
  "classifier_votes": {
    "llm": { "category": "Database", "confidence": 0.94 },
    "knn": { "category": "Database", "confidence": 0.80 },
    "centroid": { "category": "Database", "confidence": 0.84 },
    "keyword": { "category": "Database", "confidence": 0.75 }
  },
  "agreement": "4/4",
  "bonuses": ["error_code_match", "graph_confirms"],
  "reasoning": "PostgreSQL connection limit is a database configuration issue..."
}
```

---

## Stage 5: DECIDE (Route or Escalate)

```
Final confidence: 0.940
Threshold: 0.70

Decision tree:
  confidence ≥ 0.85 AND agreement 4/4  → AUTO-ROUTE (high confidence)
  confidence ≥ 0.70 AND agreement 3/4  → AUTO-ROUTE (good confidence)
  confidence ≥ 0.70 AND agreement 2/4  → ROUTE with WARNING (borderline)
  confidence < 0.70 OR agreement 1/4   → ESCALATE to human
  confidence < 0.50                     → ESCALATE + flag as "uncertain"

Our case:
  confidence = 0.940, agreement = 4/4
  → AUTO-ROUTE (high confidence) ✅

Action:
  Route to: Database Admin team (from routing_rules)
  SLA: 4 hours (high priority)
  Suggested resolution: "Kill idle connections, increase max_connections (KB-0001)"
  Recommended engineer: Arjun Nair (PostgreSQL expert)
```

---

## Handling Tricky Cases

### Case 1: "API slow after database index was dropped"

```
Stage 3 results:
  LLM:      Database (0.82)  — "root cause is dropped index"
  KNN:      Mixed — 2 Database, 2 Application, 1 Infrastructure
  Centroid: Application (0.45) — embedding is between App and DB centroids
  Keyword:  Application (api) and Database (index) — TIE

Stage 4:
  Database:    (0.40×0.82) + (0.30×0.40) + (0.20×0.30) + (0.10×0.50) = 0.558
  Application: (0.40×0.10) + (0.30×0.40) + (0.20×0.45) + (0.10×0.50) = 0.300

  Agreement: 1/4 (only LLM says Database clearly)
  Calibrated confidence: 0.558 × 0.80 = 0.446

Stage 5:
  0.446 < 0.70 → ESCALATE ⚠️

  Result: Escalated with AI's best guess "Database (45%)"
  Human reviews and decides
```

### Case 2: "Firewall blocking database port 5432"

```
Stage 3 results:
  LLM:      Network (0.78)  — "firewall is a network device, root cause is rule change"
  KNN:      Network (3/5)   — similar firewall tickets were Network
  Centroid: Network (0.62)  — closer to Network centroid
  Keyword:  TIE — firewall (Network) + database, 5432 (Database)

Stage 4:
  Network:  (0.40×0.78) + (0.30×0.60) + (0.20×0.62) + (0.10×0.50) = 0.666
  Database: (0.40×0.10) + (0.30×0.20) + (0.20×0.20) + (0.10×0.50) = 0.190

  Agreement: 3/4 (LLM, KNN, centroid agree on Network)
  Calibrated: 0.666 × 0.95 = 0.633

Stage 5:
  0.633 < 0.70 → ESCALATE ⚠️ (borderline)
  But 3/4 agree → could argue for routing with warning

  Result: Route to Network Engineering with warning "borderline confidence"
  CC: Database Admin team (secondary category)
```

### Case 3: "server down" (vague ticket)

```
Stage 1:
  Quality score: LOW (only 11 characters, no entities, no error codes)
  Maximum confidence capped at 0.75

Stage 3 results:
  LLM:      Infrastructure (0.60) — "server" = infrastructure, but very uncertain
  KNN:      No strong match (best similarity: 0.35) — too vague
  Centroid: Infrastructure (0.40) — weakly similar
  Keyword:  Infrastructure (server) → score: 1

Stage 4:
  Infrastructure: 0.40×0.60 + 0.30×0.30 + 0.20×0.40 + 0.10×0.50 = 0.460
  Capped at 0.75 due to low quality
  Agreement: 3/4 but all low confidence
  Calibrated: 0.460 × 0.75 = 0.345

Stage 5:
  0.345 < 0.70 → ESCALATE ⚠️

  Result: Escalated with request for more info
  "Please provide: Which server? What error do you see? When did it start?"
```

---

## Graceful Degradation

The system works at different capability levels depending on what's available:

```
┌──────────────────────────────────────────────────────────────────┐
│ LEVEL 4: FULL (all systems running)                              │
│ LLM + KNN + Centroid + Keywords + Graph + Error matching         │
│ Expected accuracy: ~90%+                                         │
│ Used when: Everything healthy                                    │
├──────────────────────────────────────────────────────────────────┤
│ LEVEL 3: NO GRAPH DATA (empty database)                          │
│ LLM + Keywords (no KNN, no centroid, no graph context)           │
│ Expected accuracy: ~80%                                          │
│ Used when: Fresh install, no seed data yet                       │
├──────────────────────────────────────────────────────────────────┤
│ LEVEL 2: NO LLM (Ollama is down)                                 │
│ KNN + Centroid + Keywords (no LLM)                               │
│ Expected accuracy: ~70%                                          │
│ Used when: Ollama crashed or unreachable                         │
├──────────────────────────────────────────────────────────────────┤
│ LEVEL 1: EMERGENCY (only keywords)                               │
│ Keywords only (no LLM, no database)                              │
│ Expected accuracy: ~55%                                          │
│ Used when: Both Ollama and ArangoDB are down                     │
│ All tickets at this level are flagged for human review            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Why This Architecture is Robust

### 1. No Single Point of Failure

If the LLM hallucinates → KNN and centroid correct it.
If the database is empty → LLM still classifies from its training knowledge.
If Ollama is down → KNN + centroid + keywords still work.
If everything is down → keyword rules provide emergency routing.

### 2. Mathematically Sound Confidence

Confidence isn't just the LLM's self-reported number. It's a **weighted aggregate** of 4 independent signals with calibration. This makes the confidence score **meaningful**:

- 0.90 confidence = right ~90% of the time (because calibrated)
- 0.50 confidence = truly uncertain (escalate)

### 3. Root Cause Focus

The LLM prompt explicitly says "classify by ROOT CAUSE, not symptom" with examples. The graph traversal reveals infrastructure dependencies (`depends_on` edges) that expose root causes:

```
Symptom: "OrderService 502 errors"
Graph:   OrderService → depends_on → PostgreSQL → prod-db-01 (unreachable)
Root cause: Database issue, not Application
```

### 4. Handles Edge Cases

- **Ambiguous tickets**: Low agreement between classifiers → low confidence → escalate
- **Short tickets**: Quality check → cap confidence → likely escalate
- **New issue types**: No similar past tickets → KNN and centroid weaker → LLM carries more weight → if unsure, escalate
- **Overlapping categories**: Secondary category tracked → CC'd team

### 5. Improves Over Time

Every classified ticket becomes training data:
- New ticket embedding added to collection → KNN gets better
- Category centroids recomputed periodically → centroid classifier improves
- Human overrides on escalated tickets → system learns from corrections
- Error codes added for newly discovered errors → pattern matching improves

---

## Database Fields Used at Each Stage

| Stage | Field | Collection | Purpose |
|-------|-------|-----------|---------|
| 1.1 | `description` | tickets | Text to normalize and embed |
| 1.2 | `_key` | servers, services | Match entity names in text |
| 1.2 | `pattern` | error_codes | Match error patterns in text |
| 1.3 | — | — | Quality assessment |
| 2.1 | `embedding` | tickets | Vector similarity search |
| 2.2 | `triggered_by` edges | error_codes → tickets | Past tickets with same error |
| 2.3 | `hosts`, `managed_by`, `affects`, `depends_on` edges | servers, services, teams | Graph context |
| 2.4 | `title`, `description` (fulltext index) | tickets | Keyword search |
| 3.1 | All Stage 2 results | — | LLM prompt context |
| 3.2 | `category` of 5 nearest | tickets | KNN voting |
| 3.3 | Pre-computed centroids | — (cached in Redis) | Category distance |
| 3.4 | — | — | Keyword dictionaries (in code) |
| 4 | All Stage 3 results | — | Weighted aggregation |
| 5 | `category`, `priority` | routing_rules | Route to team |
| 5 | `domain`, `sla_hours` | teams | SLA and escalation |
| 5 | `expertise` | engineers | Recommend expert |
| — | All above | audit_log | Full audit trail |

---

## Comparison: Old vs Improved Architecture

| Aspect | Old (LLM only) | Improved (4-classifier ensemble) |
|--------|----------------|----------------------------------|
| Classifiers | 1 (LLM) | 4 (LLM + KNN + Centroid + Keywords) |
| If LLM wrong | Wrong answer auto-routed | 3 other classifiers can override |
| If LLM down | System fails | 3 classifiers still work (~70% accuracy) |
| Confidence | LLM self-reported (unreliable) | Calibrated from 4 signals (reliable) |
| Root cause | Depends on prompt | Prompt + graph dependencies + past tickets |
| Ambiguous tickets | May auto-route incorrectly | Low agreement → escalated |
| New issue types | LLM guesses | LLM + escalation if uncertain |
| Improves over time | No | Yes — every ticket improves KNN + centroids |
| Expected accuracy | ~80% | ~90%+ |
