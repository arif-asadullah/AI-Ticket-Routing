# Phase 6: Ticket Lifecycle & Resolution Pipeline

## What We Did

Completed the full ticket lifecycle — from submission through resolution — so engineers can pick up, reassign, and close tickets. Also wired the orchestrator's resolution suggestions, runbook recommendations, and expert lookups into the API response.

Before Phase 6, a ticket was created and classified but then just sat there. Now, tickets flow through a real lifecycle:

```
Submit → Classify → Route → Pick Up → (Reassign?) → Resolve
```

---

## The Ticket Lifecycle

### Status Flow

```
                  ┌──────────────┐
                  │   submitted  │
                  └──────┬───────┘
                         │
              ┌──────────▼──────────┐
              │   4-Classifier AI   │
              │   (Phase 4 pipeline)│
              └──────────┬──────────┘
                         │
              confidence ≥ 0.70?
              ┌──yes─────┴────no──┐
              │                   │
       ┌──────▼──────┐    ┌──────▼──────┐
       │   routed    │    │  escalated  │
       │ (auto-sent  │    │ (human must │
       │  to team)   │    │  review)    │
       └──────┬──────┘    └──────┬──────┘
              │                   │
              └──────┬────────────┘
                     │
              ┌──────▼──────┐
              │ in_progress  │  ← Engineer picks up
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │  resolved    │  ← Engineer documents fix
              └─────────────┘
```

---

## What Was Built

### 1. Resolution in API Response (Step 3)

**Problem**: The orchestrator was already finding suggested resolutions, expert recommendations, and matching runbooks — but the API was throwing this data away. The frontend never saw it.

**Fix**: Wired the orchestrator's enrichment data through to the TicketResponse schema.

**File**: `backend/schemas/ticket.py`

New fields added to `TicketResponse`:
```python
suggested_resolution: list[str] | None     # fix steps from similar past tickets
resolution_effectiveness: float | None     # how well the suggested fix worked before (0.0-1.0)
suggested_runbook: str | None              # "KB-0003: VPN Certificate Renewal"
recommended_expert: str | None             # "Meera Patel" (from graph traversal)
```

**File**: `backend/api/tickets.py` — `create_ticket()` now maps these from the orchestrator result:
```python
TicketResponse(
    ...
    suggested_resolution=result["suggested_resolution"],
    resolution_effectiveness=result["resolution_effectiveness"],
    suggested_runbook=result["suggested_runbook"],
    recommended_expert=result["recommended_expert"],
)
```

**File**: `backend/services/orchestrator.py` — Resolution finding logic:
1. **Source 1**: Resolutions from similar tickets (same category, highest effectiveness)
2. **Source 2**: Resolutions from error-matched tickets (same error code + same category)
3. **Source 3**: Resolutions from graph context (past tickets on the same server)
4. **Runbook**: Matched by category from `runbooks` collection
5. **Expert**: First expert from graph traversal (team member with relevant expertise)

**Example response after submitting a ticket**:
```json
{
  "id": "12345",
  "category": "Database",
  "confidence_score": 0.901,
  "routed_to": "Database Admin",
  "suggested_resolution": [
    "Check pg_stat_activity for connection count",
    "Increase max_connections in postgresql.conf",
    "Restart PostgreSQL service"
  ],
  "resolution_effectiveness": 0.95,
  "suggested_runbook": "KB-0005: PostgreSQL Connection Management",
  "recommended_expert": "Meera Patel"
}
```

---

### 2. Engineer Picks Up Ticket (Step 4)

**File**: `backend/api/tickets.py` — `PATCH /api/tickets/{id}/status`

**What it does**: Lets an engineer change a ticket's status — pick it up, reassign it to another team, or escalate it.

**Request body** (`TicketStatusUpdate`):
```python
class TicketStatusUpdate(BaseModel):
    status: str           # "in_progress", "escalated", "routed"
    assigned_to: str | None   # team name (for reassignment)
    updated_by: str | None    # engineer email
```

**How it works**:
1. Validates status is one of: `in_progress`, `escalated`, `routed`
2. Rejects updates to resolved/closed tickets (400 error)
3. If `assigned_to` is provided (team reassignment):
   - Updates `routed_to` field on the ticket
   - Deletes old `assigned_to` edge (ticket → old team)
   - Creates new `assigned_to` edge (ticket → new team)
4. Writes to `audit_log` with old/new status and team
5. Returns updated ticket

**Example — Engineer picks up a ticket**:
```bash
curl -X PATCH http://localhost:8000/api/tickets/12345/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "updated_by": "arjun.nair@company.com"
  }'
```

**Example — Reassign to a different team**:
```bash
curl -X PATCH http://localhost:8000/api/tickets/12345/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "routed",
    "assigned_to": "Infrastructure Ops",
    "updated_by": "arjun.nair@company.com"
  }'
```

**Audit log entry created**:
```json
{
  "ticket_id": "12345",
  "action": "in_progress",
  "actor": "arjun.nair@company.com",
  "old_value": { "status": "routed", "team": "Database Admin" },
  "new_value": { "status": "in_progress", "team": "Database Admin" },
  "created_at": "2026-04-28T16:00:00Z"
}
```

---

### 3. Resolve Ticket (Step 5)

**File**: `backend/api/tickets.py` — `POST /api/tickets/{id}/resolve`

**What it does**: Closes a ticket by recording what was done to fix it. Feeds back into the system so future tickets with the same problem get better suggestions.

**Request body** (`TicketResolve`):
```python
class TicketResolve(BaseModel):
    resolution_steps: list[str]       # what was done to fix it
    used_ai_suggestion: str = "no"    # "yes", "partially", "no"
    used_runbook: str | None = None   # "KB-0001" or null
    resolved_by: str | None = None    # engineer email
```

**How it works**:
1. Rejects if ticket is already closed (400 error)
2. Creates a **resolution document** in `resolutions` collection:
   - `steps`: the engineer's fix steps
   - `effectiveness`: calculated from `used_ai_suggestion` (yes=1.0, partially=0.85, no=0.90)
   - `embedding`: MiniLM embedding of the resolution text (for future similarity search)
3. Creates `resolved_with` edge (ticket → resolution)
4. If a runbook was used, creates `references` edge (resolution → runbook)
5. Sets ticket status to `"resolved"` and records `resolved_at` timestamp
6. Writes to `audit_log` with full resolution details

**Example — Resolve a ticket**:
```bash
curl -X POST http://localhost:8000/api/tickets/12345/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "resolution_steps": [
      "Identified max_connections was set to 100",
      "Increased to 200 in postgresql.conf",
      "Restarted PostgreSQL service",
      "Verified connections stable for 30 minutes"
    ],
    "used_ai_suggestion": "partially",
    "used_runbook": "KB-0005",
    "resolved_by": "meera.patel@company.com"
  }'
```

**Graph edges created**:
```
tickets/12345 ──resolved_with──→ resolutions/RES-NEW-001
resolutions/RES-NEW-001 ──references──→ runbooks/KB-0005
```

**Why `used_ai_suggestion` matters**: When an engineer confirms the AI suggestion worked (`"yes"`), the resolution gets effectiveness=1.0. Next time a similar ticket comes in, this resolution ranks higher in suggestions. This is the **feedback loop** — the system learns from confirmed fixes.

---

### 4. Delete Ticket

**File**: `backend/api/tickets.py` — `DELETE /api/tickets/{id}`

Simple cleanup endpoint. Returns 204 on success, 404 if ticket doesn't exist.

---

### 5. Ticket List Filtering

**File**: `backend/api/tickets.py` — `GET /api/tickets`

Only returns user-submitted tickets (excludes seed/synthetic data). Filters by `_source` field:
```python
if doc.get("_source") in ("seed", "synthetic"):
    continue  # skip non-user tickets
```

---

## Jira Ticket Housekeeping

Updated 31 completed Jira tickets in the ATR project:
- Assigned all to Arif Asadullah
- Transitioned all from "To Do" to "Testing"

**Tickets moved to Testing**:
ATR-9, ATR-10, ATR-27, ATR-28, ATR-29, ATR-30, ATR-31, ATR-32, ATR-33, ATR-34, ATR-35, ATR-37, ATR-38, ATR-39, ATR-40, ATR-41, ATR-42, ATR-43, ATR-44, ATR-45, ATR-49, ATR-51, ATR-57, ATR-58, ATR-59, ATR-62, ATR-63, ATR-65, ATR-69, ATR-75, ATR-77

---

## File Summary

| File | What it does |
|------|-------------|
| `backend/schemas/ticket.py` | Pydantic schemas: TicketCreate, TicketStatusUpdate, TicketResolve, TicketResponse |
| `backend/api/tickets.py` | Full CRUD: create, get, list, update status, resolve, delete |
| `backend/services/orchestrator.py` | Resolution finding (3 sources), runbook lookup, expert recommendation |

## API Endpoints Summary

| Method | Endpoint | What it does |
|--------|----------|-------------|
| `POST` | `/api/tickets` | Create + classify + route ticket |
| `GET` | `/api/tickets` | List user-submitted tickets |
| `GET` | `/api/tickets/{id}` | Get single ticket with all fields |
| `PATCH` | `/api/tickets/{id}/status` | Engineer picks up / reassigns / escalates |
| `POST` | `/api/tickets/{id}/resolve` | Close ticket with resolution steps |
| `DELETE` | `/api/tickets/{id}` | Delete a ticket |
