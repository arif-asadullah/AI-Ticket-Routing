# Classification Pipeline — How Everything Works Together

## Overview

This document explains how DeskMind combines **all 3 search methods** (vector search, error matching, graph traversal) with the **LLM** to classify and route tickets. This is the full end-to-end pipeline.

## The Complete Pipeline — Step by Step

```
┌──────────────────────────────────────────────────────────────┐
│                  NEW TICKET SUBMITTED                         │
│  Title: "PostgreSQL not accepting connections on prod-db-01" │
│  Description: "prod-db-01 refusing connections since 10am.   │
│  max_connections reached at 100. FATAL: too many connections  │
│  in logs. App team reporting 502 errors on checkout page."   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  STEP 1       │
                   │  PREPARE      │
                   └───────┬───────┘
                           │
```

### Step 1: Prepare

Three things happen simultaneously:

```
                    Ticket description
                    /        |        \
                   /         |         \
                  ▼          ▼          ▼
           ┌──────────┐ ┌──────────┐ ┌──────────┐
           │ Compute   │ │ Extract  │ │ Scan for │
           │ embedding │ │ entities │ │ error    │
           │ (MiniLM)  │ │ (names)  │ │ patterns │
           └─────┬─────┘ └─────┬────┘ └─────┬────┘
                 │              │             │
                 ▼              ▼             ▼
           384 numbers    "prod-db-01"   "ERR-PG-001"
                          "PostgreSQL"    (FATAL: too
                                          many connections)
```

**a) Compute embedding**: MiniLM converts the description into 384 numbers.
- **Field used**: ticket `description`
- **Output**: `embedding` array — stored in the ticket document

**b) Extract entities**: Scan the text for known server names and service names.
- **Fields checked against**: `servers._key`, `services._key`, `services.name`
- **Output**: `["prod-db-01", "postgresql"]`

**c) Scan for error patterns**: Check if the description contains any of the 20 known error patterns.
- **Field checked against**: `error_codes.pattern`
- **Output**: `["ERR-PG-001"]`

---

### Step 2: Search (All 3 Methods in Parallel)

```
           ┌──────────────┐  ┌──────────────┐  ┌────────────────┐
           │METHOD 1       │  │METHOD 2       │  │METHOD 3         │
           │Vector Search  │  │Error Matching │  │Graph Traversal  │
           │               │  │               │  │                 │
           │Use embedding  │  │Use ERR-PG-001 │  │Start from       │
           │to find 5      │  │to find past   │  │prod-db-01 and   │
           │similar tickets│  │tickets with   │  │follow edges     │
           │               │  │same error     │  │                 │
           └──────┬────────┘  └──────┬────────┘  └───────┬─────────┘
                  │                  │                    │
                  ▼                  ▼                    ▼
           ┌──────────────┐  ┌──────────────┐  ┌────────────────┐
           │TKT-042 (0.96)│  │TKT-042       │  │Services:       │
           │TKT-078 (0.89)│  │TKT-089       │  │ PostgreSQL,    │
           │TKT-056 (0.72)│  │TKT-112       │  │ Redis          │
           │TKT-033 (0.65)│  │              │  │Team: db-admin  │
           │TKT-012 (0.58)│  │              │  │Past: TKT-042,  │
           │               │  │              │  │ TKT-056, TKT-078│
           └──────────────┘  └──────────────┘  │Expert: Arjun   │
                                                └────────────────┘
```

**Method 1 — Vector Search** (see [vector-search.md](vector-search.md)):
- Input: the 384-number embedding
- Searches: `tickets.embedding` field (via vector index)
- Returns: 5 most similar past tickets

**Method 2 — Error Matching** (see [error-matching.md](error-matching.md)):
- Input: matched error code ERR-PG-001
- Follows: `triggered_by` edges from error_code to tickets
- Returns: past tickets with the same error

**Method 3 — Graph Traversal** (see [graph-traversal.md](graph-traversal.md)):
- Input: extracted entity "prod-db-01"
- Follows: `hosts`, `managed_by`, `affects`, `depends_on`, `member_of` edges
- Returns: infrastructure context, past tickets on same server, team, experts

---

### Step 3: Collect & Deduplicate Candidate Resolutions

All 3 methods may find the same ticket (e.g., TKT-042 appears in all 3). We deduplicate and rank:

```
All candidate tickets (deduplicated):
  TKT-042 — found by: vector (0.96) + error match + graph
             resolution: "Killed idle connections, increased max_connections"
             effectiveness: 0.95
             runbook: KB-0001

  TKT-078 — found by: vector (0.89) + graph
             resolution: "Increased connection pool size"
             effectiveness: 0.85
             runbook: null

  TKT-056 — found by: vector (0.72) + graph
             resolution: "Added missing index on orders table"
             effectiveness: 0.95
             runbook: null

  TKT-089 — found by: error match only
             resolution: "Restarted connection pooler"
             effectiveness: 0.70
             runbook: null

  TKT-112 — found by: error match only
             resolution: "Waited for DB to finish startup"
             effectiveness: 0.60
             runbook: null
```

**Ranking**: Tickets found by more methods rank higher. Among ties, higher effectiveness wins.

---

### Step 4: Build LLM Prompt

Now we construct the prompt for Phi-3-mini. The prompt includes the new ticket + all the context we gathered:

```
SYSTEM:
You are DeskMind, an IT ticket classification system.

Categories: Infrastructure, Application, Security, Database, Storage, Network
Priorities: critical, high, medium, low

CONTEXT FROM KNOWLEDGE GRAPH:
- Server: prod-db-01 (database server, ap-south-1, 32GB RAM)
- Services: PostgreSQL 15.4, Redis 7.2
- Managed by: Database Admin team
- Error detected: ERR-PG-001 "FATAL: too many connections" (severity: high)
- Dependent services: OrderService, AuthService

SIMILAR PAST TICKETS:
1. "PostgreSQL max_connections reached" → Database, high
   Resolution: Killed idle connections, increased max_connections (effectiveness: 0.95)
   Runbook: KB-0001
2. "Database connection pool exhausted" → Database, high
   Resolution: Increased connection pool size (effectiveness: 0.85)
3. "Slow queries blocking production traffic" → Database, high
   Resolution: Added missing index (effectiveness: 0.95)

USER:
Classify this new ticket:
Title: "PostgreSQL not accepting connections on prod-db-01"
Description: "prod-db-01 refusing connections since 10am. max_connections reached
at 100. FATAL: too many connections in logs. App team reporting 502 errors."

Return JSON:
{
  "category": "one of the 6 categories",
  "priority": "critical|high|medium|low",
  "confidence": 0.0 to 1.0,
  "reasoning": "explain why you chose this category"
}
```

### Step 5: LLM Responds

```json
{
  "category": "Database",
  "priority": "high",
  "confidence": 0.97,
  "reasoning": "PostgreSQL connection limit reached on production database server. All 3 similar past tickets were classified as Database. Error code ERR-PG-001 is a known database issue. The 502 errors on the application side are a symptom, not the root cause."
}
```

Notice the **high confidence (0.97)** — because:
- All 3 search methods agree it's a Database issue
- 3 similar past tickets were all classified as Database
- The known error code ERR-PG-001 is linked to PostgreSQL
- The graph shows prod-db-01 is a database server managed by db-admin

---

### Step 6: Route the Ticket

```
confidence = 0.97
threshold  = 0.70 (from CONFIDENCE_THRESHOLD in .env)

0.97 >= 0.70 → AUTO-ROUTE (don't escalate)

Lookup routing_rules:
  category="Database" + priority="high" → target_team="db-admin"

Result:
  ✅ Routed to: Database Admin team
  ✅ SLA: 4 hours (high priority)
  ✅ Suggested resolution: "Kill idle connections, increase max_connections (KB-0001)"
  ✅ Recommended engineer: Arjun Nair (PostgreSQL expert)
```

If confidence were **below 0.70** (e.g., 0.55):
```
0.55 < 0.70 → ESCALATE to human

Result:
  ⚠️ Status: escalated
  ⚠️ Reason: AI confidence too low
  ⚠️ AI's best guess: Database (55%) — human to verify
```

---

### Step 7: Save Everything

The system saves:

**To `tickets` collection:**
```json
{
  "_key": "auto-generated",
  "title": "PostgreSQL not accepting connections on prod-db-01",
  "description": "prod-db-01 refusing connections since 10am...",
  "category": "Database",
  "priority": "high",
  "status": "routed",
  "confidence_score": 0.97,
  "ai_reasoning": "PostgreSQL connection limit reached...",
  "submitted_by": "kavitha.rajan@company.com",
  "embedding": [0.82, -0.15, ...],
  "created_at": "2026-04-24T10:00:00Z",
  "resolved_at": null
}
```

**To `affects` edges:**
```json
{ "_from": "tickets/new-ticket-id", "_to": "servers/prod-db-01" }
{ "_from": "tickets/new-ticket-id", "_to": "services/postgresql" }
```

**To `assigned_to` edge:**
```json
{ "_from": "tickets/new-ticket-id", "_to": "teams/db-admin" }
```

**To `triggered_by` edge:**
```json
{ "_from": "error_codes/ERR-PG-001", "_to": "tickets/new-ticket-id" }
```

**To `audit_log`:**
```json
{
  "ticket_id": "new-ticket-id",
  "action": "classified",
  "actor": "ai-phi3",
  "new_value": { "category": "Database", "priority": "high" },
  "confidence_score": 0.97,
  "reasoning": "PostgreSQL connection limit reached...",
  "created_at": "2026-04-24T10:00:05Z"
}
```

---

## Confidence Scoring — How the AI Decides How Sure It Is

The confidence score isn't just a random number from the LLM. It's calculated from **multiple signals**:

### Signal 1: LLM's Own Confidence
The LLM outputs a confidence in its JSON response. This is based on how clearly the ticket matches a category.
- "PostgreSQL connection error" → very clear → 0.95
- "Something is slow, not sure what" → vague → 0.55

### Signal 2: Agreement Among Past Tickets
If all 5 similar past tickets were classified the same category → high confidence.
If they're mixed (3 Database, 2 Network) → lower confidence.

```
All 5 similar tickets = Database → boost confidence +0.05
3 Database + 2 other → no boost
All 5 different → reduce confidence -0.10
```

### Signal 3: Error Code Match
If a known error code was found, and it points to a specific service/category → boost confidence.
- ERR-PG-001 found → service is PostgreSQL → confirms Database → +0.05

### Signal 4: Graph Context Agreement
If the graph says the server is managed by the Database team, and the LLM says Database → confirms each other → +0.03.

### Final Confidence:
```
base (from LLM)     = 0.90
+ past ticket agree  = 0.05
+ error code match   = 0.05
+ graph confirms     = 0.03
─────────────────────
= 0.97 (capped at 1.0)

vs threshold 0.70 → AUTO-ROUTE ✅
```

---

## What Happens for a Tricky Ticket?

### Example: "API slow after network change, seeing timeouts and query errors"

This ticket could be:
- **Application** (API is slow)
- **Network** (network change caused it)
- **Database** (query errors)

```
Step 1: Prepare
  Embedding computed
  Entities: none found (no specific server/service name)
  Error codes: none matched

Step 2: Search
  Vector search: mixed results
    - "NGINX 504 timeout" → Application
    - "High latency between datacenters" → Network
    - "Slow queries blocking production" → Database
  Error matching: nothing
  Graph traversal: no entity to start from

Step 3: Collect
  3 different categories from 3 results → no agreement

Step 4: LLM Prompt
  Similar tickets are mixed — Application, Network, Database
  No error code, no graph context

Step 5: LLM Responds
  {
    "category": "Network",
    "priority": "high",
    "confidence": 0.48,
    "reasoning": "The trigger was a network change, so root cause is likely Network.
     However, could also be Database if the network change affected DB connectivity."
  }

Step 6: Route
  0.48 < 0.70 → ESCALATE ⚠️
  Status: escalated
  AI's best guess: Network (48%)
  Human reviewer decides the final category
```

This is exactly how it should work — ambiguous tickets get **escalated**, not misrouted.

---

## Summary: Which Fields Power Each Step

| Step | Fields Used | Collections Involved |
|------|------------|---------------------|
| Compute embedding | `description` → `embedding` | tickets |
| Extract entities | `description` vs `servers._key`, `services._key` | tickets, servers, services |
| Error matching | `description` vs `error_codes.pattern` | tickets, error_codes |
| Vector search | `embedding` (vector index) | tickets |
| Graph traversal | edges: hosts, managed_by, affects, depends_on, member_of | all edge collections |
| Get resolutions | `resolved_with` edge → `resolutions.steps`, `effectiveness` | resolutions |
| Get runbooks | `references` edge → `runbooks.title`, `steps` | runbooks |
| LLM classification | prompt built from all above context | — (sent to Ollama) |
| Confidence scoring | LLM output + past ticket agreement + error match + graph context | — (computed in code) |
| Routing | `routing_rules.category` + `priority` → `target_team` | routing_rules, teams |
| Audit | all above saved to `audit_log` | audit_log |

---

## The Full Flow Diagram (One Page Summary)

```
SUBMIT TICKET
      │
      ▼
┌─── PREPARE ────────────────────────────────┐
│ 1. Compute embedding (MiniLM → 384 numbers)│
│ 2. Extract entities (server/service names)  │
│ 3. Match error patterns                     │
└─────────────────────┬──────────────────────┘
                      │
      ┌───────────────┼───────────────┐
      ▼               ▼               ▼
┌──────────┐   ┌──────────┐   ┌──────────────┐
│ VECTOR   │   │ ERROR    │   │ GRAPH        │
│ SEARCH   │   │ MATCH    │   │ TRAVERSAL    │
│ (meaning)│   │ (pattern)│   │ (connections)│
└────┬─────┘   └────┬─────┘   └──────┬───────┘
     │              │                 │
     └───────┬──────┘                 │
             ▼                        ▼
      Past tickets              Infrastructure
      + resolutions              context
             │                        │
             └────────┬───────────────┘
                      ▼
              BUILD LLM PROMPT
              (ticket + context)
                      │
                      ▼
              LLM CLASSIFIES
              {category, priority,
               confidence, reasoning}
                      │
                      ▼
              CONFIDENCE CHECK
              ≥ 0.70? ──YES──→ AUTO-ROUTE → team
                │
                NO
                │
                ▼
              ESCALATE → human reviews
```
