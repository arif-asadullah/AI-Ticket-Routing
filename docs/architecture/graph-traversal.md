# Graph Traversal — Finding Context Through Connections

## What Problem Does This Solve?

Vector search finds tickets with similar **text**. Error matching finds tickets with the same **error code**. But sometimes the most useful context isn't in the text — it's in the **connections** between infrastructure components.

Example: A ticket says "prod-db-01 is slow but no errors in logs." Vector search might not find anything useful (no specific error to match). But the **graph** knows:
- prod-db-01 runs PostgreSQL and Redis
- prod-db-01 is managed by Database Admin team
- 3 past tickets affected this same server
- Those tickets were resolved by adding indexes and increasing memory

## Real-World Analogy

Imagine a detective investigating a crime at a restaurant:
- **Vector search** = check if similar crimes happened anywhere in the city
- **Error matching** = check if the same fingerprints were found at other crime scenes
- **Graph traversal** = investigate the restaurant's connections: Who works there? Who supplies them? What other businesses are in the same building? Were there issues next door?

Graph traversal follows **relationships** to find context that text alone can't reveal.

## How the Knowledge Graph is Connected

```
                                    ┌────────────┐
                               ┌───→│   teams    │←──────────────┐
                               │    └────────────┘               │
                        member_of         ↑                assigned_to
                               │     managed_by                  │
                        ┌──────┴───┐      │           ┌─────────┴──┐
                        │engineers │  ┌───┴────┐      │  tickets   │
                        └──────────┘  │servers │      └──┬──┬──┬───┘
                                      └───┬────┘   affects│  │  │resolved_with
                                     hosts│        ┌─────┘  │  │
                                      ┌───┴────┐   │   triggered │
                                      │services│←──┘     _by│  ↓
                                      └───┬────┘        │  ┌────────────┐
                                   depends_on│     ┌────┴──┤resolutions │
                                          ↓↑  │error  │ └──────┬─────┘
                                              │_codes │  references
                                              └───────┘        ↓
                                                        ┌──────────┐
                                                        │ runbooks │
                                                        └──────────┘
```

Every arrow is an **edge** — a relationship stored in the database. Graph traversal means **following these arrows** to find connected information.

## How It Works — Step by Step

### Example Ticket: "prod-db-01 is slow, response times over 10 seconds"

### Step 1: Extract Entities from Ticket Text

The system scans the description for known server names, service names, and error codes:

```
"prod-db-01 is slow, response times over 10 seconds"
     ↑
     └── Found: server "prod-db-01" (exists in servers collection)
```

### Step 2: Start Traversal from the Server Node

Starting at `servers/prod-db-01`, follow edges outward:

```
                    servers/prod-db-01
                    (database, ap-south-1, 32GB RAM)
                           │
              ┌────────────┼────────────────┐
              │            │                │
         hosts│       managed_by│       affects (reverse)│
              ▼            ▼                ▼
        ┌──────────┐  ┌──────────┐   ┌──────────────────┐
        │postgresql │  │ db-admin │   │ Past tickets on  │
        │redis      │  │  team    │   │ this server:     │
        └──────────┘  └──────────┘   │ TKT-042, TKT-056 │
                                      │ TKT-078           │
                                      └──────────────────┘
```

**One hop** from prod-db-01, we already know:
- What services run on it (PostgreSQL, Redis)
- Who manages it (Database Admin team)
- What past tickets affected it (TKT-042, TKT-056, TKT-078)

### Step 3: Go Deeper — Follow More Edges

From the past tickets, follow `resolved_with` to get resolutions:

```
TKT-042 ──resolved_with──→ "Killed idle connections, increased max_connections"
                            effectiveness: 0.95

TKT-056 ──resolved_with──→ "Added missing index on orders table"
                            effectiveness: 0.95

TKT-078 ──resolved_with──→ "Cleaned up old logs, freed 50GB"
                            effectiveness: 0.80
```

From the team, follow `member_of` (reverse) to find engineers:

```
teams/db-admin ←──member_of── Arjun Nair (PostgreSQL, Redis expert)
               ←──member_of── Meera Patel (replication, tuning expert)
```

### Step 4: Check Service Dependencies

From PostgreSQL, follow `depends_on` (reverse) to see what breaks if PostgreSQL is slow:

```
services/postgresql ←──depends_on── order-service
                    ←──depends_on── auth-service
```

Now we know: if PostgreSQL is slow, **OrderService and AuthService are also affected**.

### The Full Picture After Traversal

```
Starting from: prod-db-01

What runs on it:     PostgreSQL, Redis
Who manages it:      Database Admin (Arjun Nair, Meera Patel)
Past issues:         3 tickets (connection limit, slow queries, disk space)
Best past fix:       "Added missing index" (0.95 effectiveness)
Services affected:   OrderService, AuthService
Datacenter:          ap-south-1
```

All this context is sent to the LLM along with the new ticket, so it can make a **much better** classification and suggestion.

## Which Database Fields Are Involved?

### Entity Extraction (Step 1)

| Collection | Field | How it's used |
|-----------|-------|--------------|
| `servers` | `_key` | Match "prod-db-01" in ticket text → find server node |
| `services` | `_key` | Match "PostgreSQL" in ticket text → find service node |
| `servers` | `type`, `datacenter`, `ram_gb` | Context about the server |

### Edge Traversal (Steps 2-4)

| Edge | From → To | What it reveals |
|------|-----------|----------------|
| `hosts` | server → service | What software runs on this server |
| `managed_by` | server → team | Who's responsible |
| `affects` (reversed) | server ← ticket | Past tickets on this server |
| `resolved_with` | ticket → resolution | How past tickets were fixed |
| `references` | resolution → runbook | Which guide was followed |
| `depends_on` (reversed) | service ← service | What depends on this service |
| `member_of` (reversed) | team ← engineer | Who's on the team + their expertise |

### Engineer Selection

| Collection | Field | How it's used |
|-----------|-------|--------------|
| `engineers` | `expertise` | Match expertise to the problem (e.g., "PostgreSQL" in expertise list) |
| `engineers` | `name`, `email` | Recommend specific person |

## The AQL Query

This is the actual query that traverses the graph from a server:

```aql
// @serverKey = "prod-db-01" (extracted from ticket text)

// What runs on this server?
LET hosted_services = (
  FOR svc IN 1..1 OUTBOUND CONCAT("servers/", @serverKey) hosts
    RETURN svc.name
)

// Who manages it?
LET managing_team = FIRST(
  FOR team IN 1..1 OUTBOUND CONCAT("servers/", @serverKey) managed_by
    RETURN team
)

// Past tickets on this server
LET past_tickets = (
  FOR ticket IN 1..1 INBOUND CONCAT("servers/", @serverKey) affects
    FILTER ticket.status == "closed"
    SORT ticket.created_at DESC
    LIMIT 5
    RETURN ticket
)

// Resolutions for those tickets (best first)
LET past_resolutions = (
  FOR ticket IN past_tickets
    FOR res IN 1..1 OUTBOUND ticket resolved_with
      SORT res.effectiveness DESC
      RETURN {
        ticket_title: ticket.title,
        steps: res.steps,
        effectiveness: res.effectiveness
      }
)

// Team members with relevant expertise
LET experts = (
  FOR eng IN 1..1 INBOUND managing_team._id member_of
    RETURN { name: eng.name, role: eng.role, expertise: eng.expertise }
)

// What depends on the services running here?
LET dependent_services = (
  FOR svc IN 1..1 OUTBOUND CONCAT("servers/", @serverKey) hosts
    FOR dependent IN 1..1 INBOUND svc depends_on
      RETURN DISTINCT dependent.name
)

RETURN {
  server: @serverKey,
  services: hosted_services,
  team: managing_team.name,
  past_tickets: LENGTH(past_tickets),
  best_resolution: FIRST(past_resolutions),
  experts: experts,
  dependent_services: dependent_services
}
```

**Result:**
```json
{
  "server": "prod-db-01",
  "services": ["PostgreSQL", "Redis"],
  "team": "Database Admin",
  "past_tickets": 3,
  "best_resolution": {
    "ticket_title": "Slow queries blocking production traffic",
    "steps": ["Added missing index on orders table", "Ran ANALYZE"],
    "effectiveness": 0.95
  },
  "experts": [
    { "name": "Arjun Nair", "role": "Senior DBA", "expertise": ["PostgreSQL", "Redis"] },
    { "name": "Meera Patel", "role": "DBA", "expertise": ["PostgreSQL", "replication"] }
  ],
  "dependent_services": ["OrderService", "AuthService"]
}
```

## How Many Hops?

A "hop" is one edge traversal. More hops = more context but slower.

| Hops | What you find | Example |
|------|-------------|---------|
| **1 hop** | Direct connections | prod-db-01 → PostgreSQL (hosts) |
| **2 hops** | Connections of connections | prod-db-01 → PostgreSQL → OrderService (depends_on, reversed) |
| **3 hops** | Deep context | prod-db-01 → PostgreSQL → OrderService → NGINX (depends_on chain) |

DeskMind uses **2 hops max** — enough context without being slow.

## When Does Graph Traversal NOT Work?

| Situation | Why | What helps instead |
|-----------|-----|--------------------|
| Ticket doesn't mention any server or service name | No starting node for traversal | Vector search, error matching |
| Server is new (just added, no past tickets) | No `affects` edges to follow | Vector search finds similar issues on other servers |
| Issue is purely about a process, not infrastructure | "Need to reset my password" — no server involved | LLM classifies from keywords, routing rules |

## Graph Traversal vs Vector Search

| | Graph Traversal | Vector Search |
|---|---|---|
| **Finds** | Connected infrastructure context | Tickets with similar meaning |
| **Starting point** | A server or service name in the ticket | The ticket's text embedding |
| **Strength** | Root cause analysis (dependency chains) | Finding similar past problems |
| **Weakness** | Needs entity names in ticket text | Misses infrastructure context |
| **Best for** | "prod-db-01 is slow" (clear server mentioned) | "Database connections timing out" (no server name) |

That's why DeskMind uses **both** — vector search finds similar problems, graph traversal provides infrastructure context.
