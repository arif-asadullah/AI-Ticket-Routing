# Graph Definition & Query Examples

This document explains the DeskMind graph — how it's defined, how to query it, and real examples you can run.

## What is a Named Graph?

In ArangoDB, a "named graph" is a formal definition that says: "These edge collections connect these document collections." It's like a blueprint that tells ArangoDB: "This is how my data is structured."

Without a named graph, edges still work — but you'd have to manually specify which collections to traverse every time. With a named graph, you just say "traverse the deskmind graph" and ArangoDB knows where to look.

## DeskMind Graph Definition

**Graph name**: `deskmind_graph`

### Edge definitions (what connects to what):

| Edge Collection | From Collections | To Collections |
|----------------|-----------------|----------------|
| `hosts` | servers | services |
| `managed_by` | servers, services | teams |
| `depends_on` | services | services |
| `member_of` | engineers | teams |
| `affects` | tickets | servers, services |
| `assigned_to` | tickets | teams |
| `resolved_with` | tickets | resolutions |
| `references` | resolutions | runbooks |
| `triggered_by` | error_codes | tickets |

### Visual diagram:

```
                          ┌────────────┐
                     ┌───→│   teams    │←──────────────┐
                     │    └────────────┘               │
              member_of         ↑                 assigned_to
                     │     managed_by                   │
              ┌──────┴───┐      │           ┌──────────┴┐
              │engineers │  ┌───┴────┐      │  tickets  │
              └──────────┘  │servers │      └──┬──┬──┬──┘
                            └───┬────┘    affects│  │  │resolved_with
                           hosts│         ┌─────┘  │  │
                            ┌───┴────┐    │        │  ↓
                            │services│←───┘  triggered ┌───────────┐
                            └───┬────┘       _by│  │resolutions│
                         depends_on│         │     └──────┬────┘
                                ↓↑      ┌────┴──────┐references
                                   │error_codes │     ↓
                                   └────────────┘┌──────────┐
                                                 │ runbooks │
                                                 └──────────┘
```

---

## How to Create the Graph

This is the AQL/JavaScript code to create the graph in ArangoDB. The `seed_db.py` script runs this automatically, but here's what it does:

```javascript
// In ArangoDB Web UI → Collections → Create all document collections first:
// tickets, teams, engineers, servers, services, network_devices,
// error_codes, runbooks, resolutions, routing_rules

// Then create edge collections:
// hosts, managed_by, depends_on, member_of, affects,
// assigned_to, resolved_with, references, triggered_by

// Then create the named graph:
var graph = require("@arangodb/general-graph");

graph._create("deskmind_graph", [
  graph._relation("hosts",        ["servers"],      ["services"]),
  graph._relation("managed_by",   ["servers", "services"], ["teams"]),
  graph._relation("depends_on",   ["services"],     ["services"]),
  graph._relation("member_of",    ["engineers"],    ["teams"]),
  graph._relation("affects",      ["tickets"],      ["servers", "services"]),
  graph._relation("assigned_to",  ["tickets"],      ["teams"]),
  graph._relation("resolved_with",["tickets"],      ["resolutions"]),
  graph._relation("references",   ["resolutions"],  ["runbooks"]),
  graph._relation("triggered_by", ["error_codes"],  ["tickets"])
]);
```

---

## Query Examples

These are real AQL queries you can run in the ArangoDB Web UI (http://localhost:8530 → Queries tab).

### 1. Find which team manages a server

**Question**: "Who manages prod-db-01?"

```aql
FOR v, e IN 1..1 OUTBOUND "servers/prod-db-01" managed_by
  RETURN v.name
```

**Result**: `"Database Admin"`

**How it works**: Start at `servers/prod-db-01`, follow one `managed_by` edge outward, return the team name.

---

### 2. Find what services run on a server

**Question**: "What's running on prod-db-01?"

```aql
FOR v, e IN 1..1 OUTBOUND "servers/prod-db-01" hosts
  RETURN { service: v.name, version: v.version, port: v.port }
```

**Result**:
```json
[
  { "service": "PostgreSQL", "version": "15.4", "port": 5432 },
  { "service": "Redis", "version": "7.0", "port": 6379 }
]
```

---

### 3. Find the full dependency chain

**Question**: "If PostgreSQL goes down, what else breaks?"

```aql
FOR v, e IN 1..3 INBOUND "services/postgresql" depends_on
  RETURN DISTINCT v.name
```

**Result**: `["OrderService", "ReportService", "APIGateway"]`

**How it works**: Start at PostgreSQL, follow `depends_on` edges **backward** (who depends on me?) up to 3 levels deep.

---

### 4. Find past tickets for a server

**Question**: "What tickets have been reported about prod-db-01?"

```aql
FOR v, e IN 1..1 INBOUND "servers/prod-db-01" affects
  SORT v.created_at DESC
  RETURN { id: v._key, title: v.title, status: v.status, date: v.created_at }
```

**Result**:
```json
[
  { "id": "12345", "title": "PostgreSQL max_connections reached", "status": "resolved", "date": "2026-04-15" },
  { "id": "12280", "title": "High CPU on prod-db-01", "status": "closed", "date": "2026-03-20" }
]
```

---

### 5. Find how a past ticket was resolved + which runbook was used

**Question**: "How was ticket #12345 fixed, and was there a runbook?"

```aql
FOR ticket IN tickets FILTER ticket._key == "12345"
  FOR resolution IN 1..1 OUTBOUND ticket resolved_with
    LET runbook = (
      FOR rb IN 1..1 OUTBOUND resolution references
        RETURN rb
    )
    RETURN {
      ticket: ticket.title,
      fix_steps: resolution.steps,
      effectiveness: resolution.effectiveness,
      runbook: runbook[0].title
    }
```

**Result**:
```json
{
  "ticket": "PostgreSQL max_connections reached",
  "fix_steps": ["Checked max_connections was 100", "Increased to 200", "Restarted PostgreSQL"],
  "effectiveness": 0.95,
  "runbook": "PostgreSQL connection limit exceeded"
}
```

---

### 6. Find the right team using routing rules

**Question**: "Category is Database, priority is high — which team?"

```aql
FOR rule IN routing_rules
  FILTER rule.category == "Database"
  AND rule.priority == "high"
  AND rule.is_active == true
  FOR team IN teams FILTER team._key == rule.target_team
    RETURN { team: team.name, sla_hours: team.sla_hours.high }
```

**Result**: `{ "team": "Database Admin", "sla_hours": 4 }`

---

### 7. Find an expert for a specific technology

**Question**: "Who on the Database Admin team knows PostgreSQL?"

```aql
FOR eng, e IN 1..1 INBOUND "teams/db-admin" member_of
  FILTER "PostgreSQL" IN eng.expertise
  RETURN { name: eng.name, role: eng.role, expertise: eng.expertise }
```

**Result**:
```json
{ "name": "Alex Chen", "role": "Senior DBA", "expertise": ["PostgreSQL", "Redis", "backup-recovery"] }
```

---

### 8. The full GraphRAG query (what the AI actually does)

**Question**: "New ticket about PostgreSQL connection issues — find similar past tickets, their resolutions, relevant runbooks, and the responsible team."

```aql
// Step 1: Find the server and team
LET server = DOCUMENT("servers/prod-db-01")
LET team = FIRST(
  FOR t IN 1..1 OUTBOUND server managed_by RETURN t
)

// Step 2: Find past tickets on this server
LET past_tickets = (
  FOR ticket IN 1..1 INBOUND server affects
    FILTER ticket.status == "resolved"
    SORT ticket.created_at DESC
    LIMIT 5
    RETURN ticket
)

// Step 3: Get resolutions for those tickets
LET resolutions = (
  FOR ticket IN past_tickets
    FOR res IN 1..1 OUTBOUND ticket resolved_with
      SORT res.effectiveness DESC
      RETURN { ticket: ticket.title, steps: res.steps, effectiveness: res.effectiveness }
)

// Step 4: Find relevant runbooks
LET runbooks = (
  FOR ticket IN past_tickets
    FOR res IN 1..1 OUTBOUND ticket resolved_with
      FOR rb IN 1..1 OUTBOUND res references
        RETURN DISTINCT rb.title
)

RETURN {
  server: server._key,
  responsible_team: team.name,
  past_tickets: LENGTH(past_tickets),
  best_resolution: FIRST(resolutions),
  relevant_runbooks: runbooks
}
```

**Result**:
```json
{
  "server": "prod-db-01",
  "responsible_team": "Database Admin",
  "past_tickets": 3,
  "best_resolution": {
    "ticket": "PostgreSQL max_connections reached",
    "steps": ["Increased max_connections to 200", "Restarted PostgreSQL"],
    "effectiveness": 0.95
  },
  "relevant_runbooks": ["PostgreSQL connection limit exceeded"]
}
```

This is the power of GraphRAG — one traversal gives you: the team, past incidents, proven fixes, and documentation. A traditional database would need 5+ separate queries.

---

## Graph Visualization

In ArangoDB Web UI:
1. Go to **Graphs** tab (left sidebar)
2. Click **deskmind_graph**
3. Click on any node to see it and its connections
4. Drag nodes to rearrange

This visual tool helps you understand how your data is connected and verify that edges are correct.
