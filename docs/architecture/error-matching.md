# Error Code Pattern Matching — The Fast Shortcut

## What Problem Does This Solve?

Sometimes a ticket contains a **known error message** like `FATAL: too many connections` or `OOMKilled`. These errors have been seen before — we know exactly what they mean and which past tickets had the same error.

Instead of waiting for vector search and AI, we can **instantly** match the error and find past resolutions.

## Real-World Analogy

Imagine a doctor's office:
- **Vector search** = doctor examines the patient, thinks about symptoms, consults textbooks → slow but thorough
- **Error matching** = patient shows a rash. Doctor immediately recognizes it as chickenpox → fast because it's a known pattern

Error matching is the **"I've seen this before"** shortcut.

## How It Works — Step by Step

### Step 1: Scan Ticket Description for Known Patterns

We have 20 known error patterns in the `error_codes` collection:

```
ERR-PG-001  → "FATAL: too many connections"
ERR-K8S-001 → "OOMKilled"
ERR-NFS-001 → "NFS: stale file handle"
ERR-SSL-001 → "certificate has expired"
... and 16 more
```

When a new ticket comes in, we scan its description text for these patterns:

```
New ticket description:
"prod-db-01 is throwing FATAL: too many connections error.
 Application team reporting 502 errors on checkout."

Scan result:
  ✅ Match: "FATAL: too many connections" → ERR-PG-001
  ✅ Match: "502" → could be ERR-NGINX-001 (but 502 in description is about the symptom, not the error code itself)
```

### Step 2: Follow `triggered_by` Edges to Find Past Tickets

The `triggered_by` edge connects error codes to past tickets that had the same error:

```
error_codes/ERR-PG-001
        │
        │ triggered_by (edge)
        │
        ├──→ tickets/TKT-042  "PostgreSQL max_connections reached"
        ├──→ tickets/TKT-089  "PostgreSQL connection limit on prod-db-02"
        └──→ tickets/TKT-112  "Database refusing connections after restart"
```

### Step 3: Get Their Resolutions (ranked by effectiveness)

```
TKT-042 ──resolved_with──→ Resolution: "Killed idle connections, increased max_connections"
                            effectiveness: 0.95  ← BEST

TKT-089 ──resolved_with──→ Resolution: "Restarted connection pooler"
                            effectiveness: 0.70

TKT-112 ──resolved_with──→ Resolution: "Waited for DB to finish startup"
                            effectiveness: 0.60
```

### Step 4: Return Best Resolution

The resolution with the highest effectiveness (0.95) is suggested first.

## The Complete Flow Diagram

```
New ticket: "prod-db-01 throwing FATAL: too many connections"
        │
        ▼
┌──────────────────────────────────┐
│ SCAN for known error patterns    │
│                                  │
│ Check description against all    │
│ 20 patterns in error_codes       │
│                                  │
│ ✅ Found: ERR-PG-001             │
│ "FATAL: too many connections"    │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ FIND past tickets with same      │
│ error via triggered_by edges     │
│                                  │
│ ERR-PG-001 → TKT-042 (0.95)     │
│            → TKT-089 (0.70)     │
│            → TKT-112 (0.60)     │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ GET resolutions (best first)     │
│                                  │
│ TKT-042's resolution:            │
│ 1. Kill idle connections          │
│ 2. Increase max_connections       │
│ 3. Restart PostgreSQL             │
│ effectiveness: 0.95               │
│                                  │
│ References: KB-0001               │
└──────────────────────────────────┘
```

## Which Database Fields Are Involved?

| Step | Collection | Field | Purpose |
|------|-----------|-------|---------|
| 1 | `error_codes` | `pattern` | The error text to match against ticket description |
| 1 | `error_codes` | `_key` | Error code ID (e.g., ERR-PG-001) |
| 1 | `error_codes` | `severity` | Pre-defined severity of this error |
| 1 | `error_codes` | `service` | Which service produces this error |
| 2 | `triggered_by` | `_from`, `_to` | Edge: error_code → ticket |
| 3 | `resolved_with` | `_from`, `_to` | Edge: ticket → resolution |
| 3 | `resolutions` | `steps` | The fix steps |
| 3 | `resolutions` | `effectiveness` | How well it worked (0.0-1.0) |
| 4 | `references` | `_from`, `_to` | Edge: resolution → runbook |
| 4 | `runbooks` | `title`, `steps` | The documented procedure |

## The AQL Query

```aql
// @description = the new ticket's description text

// Step 1: Find matching error codes
LET matched_errors = (
  FOR err IN error_codes
    FILTER CONTAINS(LOWER(@description), LOWER(err.pattern))
    RETURN err
)

// Step 2: For each error, find past tickets
LET past_tickets = (
  FOR err IN matched_errors
    FOR ticket IN 1..1 OUTBOUND err triggered_by
      FILTER ticket.status == "closed"
      RETURN ticket
)

// Step 3: Get their resolutions, ranked by effectiveness
FOR ticket IN past_tickets
  FOR res IN 1..1 OUTBOUND ticket resolved_with
    SORT res.effectiveness DESC
    LIMIT 3

    LET runbook = FIRST(
      FOR rb IN 1..1 OUTBOUND res references
        RETURN rb
    )

    RETURN {
      error_code: matched_errors[0]._key,
      past_ticket: ticket.title,
      resolution_steps: res.steps,
      effectiveness: res.effectiveness,
      runbook: runbook.title
    }
```

## When Does Error Matching NOT Work?

| Situation | Why | What helps instead |
|-----------|-----|--------------------|
| No known error in the ticket | User describes problem in their own words, no error code | Vector search, LLM classification |
| New error not in our database | We haven't seen this error before | LLM classifies from its knowledge, error added to database later |
| Ambiguous error text | "timeout" appears in many error patterns | Vector search + graph traversal for more context |

## Error Matching vs Vector Search

| | Error Matching | Vector Search |
|---|---|---|
| **Speed** | Instant (string match) | Fast (vector index, ~10ms) |
| **When it works** | Known errors only | Any ticket text |
| **Accuracy** | 100% if pattern matches | ~90% (approximate similarity) |
| **Coverage** | Only 20 patterns currently | Covers all tickets |

That's why we use **both** — error matching is a fast shortcut, vector search is the comprehensive backup.
