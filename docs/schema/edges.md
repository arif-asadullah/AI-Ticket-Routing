# Edge Collections (Relationships)

Edges are the connections between documents. They are what make ArangoDB a **graph database** — without edges, it's just a regular document database.

## What is an edge?

An edge is a document that says: "This thing is connected to that thing, and here's how."

Every edge has:
- `_from` — the source document (format: `collection_name/document_key`)
- `_to` — the target document
- Optional extra fields (like timestamps or labels)

### Example:

```json
{
  "_from": "servers/prod-db-01",
  "_to": "services/postgresql"
}
```

This means: "prod-db-01 runs PostgreSQL."

## Why edges matter for DeskMind

Without edges, the AI can only look at one ticket in isolation. With edges, it can **traverse the graph** to find context:

```
Ticket: "prod-db-01 not responding"
    ↓ (look up server)
Server: prod-db-01 (database, 32GB RAM, dc-east-1)
    ↓ hosts (what runs on it?)
Service: PostgreSQL 15.4
    ↓ managed_by (who manages it?)
Team: Database Admin
    ↓ member_of (who's on the team?)
Engineer: Alex Chen (Senior DBA, PostgreSQL expert)
    ↓ (check past tickets on this server)
Past ticket: TKT-042 "PostgreSQL max_connections" → resolved by increasing limit
```

One query, follows the connections. This is GraphRAG in action.

---

## Edge 1: `hosts`

### What it means
A server **runs** a service.

### Why it exists
To answer: "Which server runs PostgreSQL?" or "What services are on prod-db-01?" This is the foundation of infrastructure mapping.

### Diagram
```
┌──────────────┐         hosts          ┌──────────────┐
│ servers/     │ ────────────────────→  │ services/    │
│ prod-db-01   │                        │ postgresql   │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A building **houses** a business. The office building at 123 Main St houses the accounting firm.

### Example edges

```json
{ "_from": "servers/prod-db-01", "_to": "services/postgresql" }
{ "_from": "servers/prod-db-01", "_to": "services/redis" }
{ "_from": "servers/prod-app-01", "_to": "services/order-service" }
{ "_from": "servers/prod-web-01", "_to": "services/nginx" }
```

### What queries it enables
- "Which servers run PostgreSQL?" → Find all `hosts` edges where `_to = services/postgresql`
- "What services are on prod-db-01?" → Find all `hosts` edges where `_from = servers/prod-db-01`
- "If prod-db-01 goes down, which services are affected?" → All services linked via `hosts`

---

## Edge 2: `managed_by`

### What it means
A server or service is **owned/managed by** a team.

### Why it exists
To answer: "Who is responsible for prod-db-01?" Even before AI classification, if the ticket mentions a server name, the system can immediately find the responsible team by following this edge.

### Diagram
```
┌──────────────┐       managed_by       ┌──────────────┐
│ servers/     │ ────────────────────→  │ teams/       │
│ prod-db-01   │                        │ db-admin     │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A hospital ward is **managed by** a department. ICU is managed by Emergency Medicine.

### Example edges

```json
{ "_from": "servers/prod-db-01", "_to": "teams/db-admin" }
{ "_from": "servers/prod-db-02", "_to": "teams/db-admin" }
{ "_from": "servers/prod-app-01", "_to": "teams/app-support" }
{ "_from": "servers/fw-prod-01", "_to": "teams/network-eng" }
{ "_from": "services/postgresql", "_to": "teams/db-admin" }
```

### What queries it enables
- "Who manages prod-db-01?" → Follow `managed_by` edge → Database Admin
- "Which servers does the Infrastructure team manage?" → Find all `managed_by` edges where `_to = teams/infra-ops`

---

## Edge 3: `depends_on`

### What it means
A service **requires** another service to function.

### Why it exists
Root cause analysis. When "OrderService is slow", the problem might not be OrderService itself — it might be PostgreSQL (which OrderService depends on) or Redis (its cache). The AI traverses `depends_on` edges to find the real cause.

### Diagram
```
┌──────────────┐       depends_on       ┌──────────────┐
│ services/    │ ────────────────────→  │ services/    │
│ order-service│                        │ postgresql   │
└──────────────┘                        └──────────────┘
         │
         │          depends_on          ┌──────────────┐
         └──────────────────────────→  │ services/    │
                                        │ redis        │
                                        └──────────────┘
```

### Real-world analogy
A restaurant **depends on** its kitchen, its ingredient suppliers, and its electricity. If the power goes out, the restaurant can't serve food — but the problem is the power, not the restaurant.

### Example edges

```json
{ "_from": "services/order-service", "_to": "services/postgresql" }
{ "_from": "services/order-service", "_to": "services/redis" }
{ "_from": "services/api-gateway", "_to": "services/order-service" }
{ "_from": "services/api-gateway", "_to": "services/auth-service" }
{ "_from": "services/nginx", "_to": "services/api-gateway" }
```

### What queries it enables
- "What does OrderService depend on?" → Follow `depends_on` → PostgreSQL, Redis
- "If PostgreSQL goes down, what else breaks?" → Reverse traversal: find all services that `depend_on` PostgreSQL → OrderService, ReportService, etc.
- "What's the full dependency chain from user to database?" → nginx → api-gateway → order-service → postgresql (multi-hop traversal)

---

## Edge 4: `member_of`

### What it means
An engineer **belongs to** a team.

### Why it exists
To recommend specific people. When routing a Database ticket, the AI can traverse: `teams/db-admin` ← `member_of` ← find engineers with relevant expertise.

### Diagram
```
┌──────────────┐       member_of        ┌──────────────┐
│ engineers/   │ ────────────────────→  │ teams/       │
│ Alex Chen    │                        │ db-admin     │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
An employee **works in** a department.

### Example edges

```json
{ "_from": "engineers/98765", "_to": "teams/db-admin" }
{ "_from": "engineers/98766", "_to": "teams/db-admin" }
{ "_from": "engineers/98767", "_to": "teams/infra-ops" }
{ "_from": "engineers/98768", "_to": "teams/network-eng" }
```

### What queries it enables
- "Who's on the Database Admin team?" → Find all `member_of` edges where `_to = teams/db-admin`
- "Which team is Alex Chen on?" → Follow `member_of` from engineers/98765

---

## Edge 5: `affects`

### What it means
A ticket **is about** a specific server or service.

### Why it exists
Historical tracking. When a new ticket mentions prod-db-01, the AI can check: "How many past tickets affected this server? Were they all Database issues? Is this server particularly problematic?" This pattern recognition is only possible with edges linking tickets to infrastructure.

### Diagram
```
┌──────────────┐        affects         ┌──────────────┐
│ tickets/     │ ────────────────────→  │ servers/     │
│ 12345        │                        │ prod-db-01   │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A patient's medical visit **relates to** a body part. "Visit #5 was about the left knee." Over time, you see a pattern: 5 visits about the left knee → recommend knee replacement, not another painkiller.

### Example edges

```json
{ "_from": "tickets/12345", "_to": "servers/prod-db-01" }
{ "_from": "tickets/12345", "_to": "services/postgresql" }
{ "_from": "tickets/12346", "_to": "servers/prod-web-01" }
{ "_from": "tickets/12346", "_to": "services/nginx" }
```

### What queries it enables
- "What past tickets affected prod-db-01?" → Find all `affects` edges where `_to = servers/prod-db-01`
- "Is this server having recurring issues?" → Count `affects` edges for this server in the last 30 days
- "Which servers have the most tickets?" → Aggregate `affects` edges by `_to`

---

## Edge 6: `assigned_to`

### What it means
A ticket was **sent to** a team for handling.

### Why it exists
Routing history. Shows which team is handling each ticket. Used for dashboards ("Database Admin has 15 open tickets") and load balancing ("this team is overloaded, route to another team").

### Diagram
```
┌──────────────┐      assigned_to       ┌──────────────┐
│ tickets/     │ ────────────────────→  │ teams/       │
│ 12345        │                        │ db-admin     │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A work order **assigned to** a contractor.

### Example edges

```json
{ "_from": "tickets/12345", "_to": "teams/db-admin" }
{ "_from": "tickets/12346", "_to": "teams/infra-ops" }
{ "_from": "tickets/12347", "_to": "teams/network-eng" }
```

### What queries it enables
- "How many tickets is each team handling?" → Count `assigned_to` edges grouped by `_to`
- "Show all open tickets for Database Admin" → Find `assigned_to` where `_to = teams/db-admin`, then filter tickets by status = "open"

---

## Edge 7: `resolved_with`

### What it means
A ticket was **fixed by** a specific resolution.

### Why it exists
This is the core of learning. When a new ticket comes in:
1. Find similar past tickets (via embedding similarity)
2. Follow `resolved_with` to get the resolution
3. Suggest that resolution for the new ticket

Without this edge, past fixes are lost knowledge.

### Diagram
```
┌──────────────┐     resolved_with      ┌──────────────┐
│ tickets/     │ ────────────────────→  │ resolutions/ │
│ 12345        │                        │ 54321        │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A patient's diagnosis was **treated with** a specific prescription. Next patient with similar symptoms → check what worked before.

### Example edges

```json
{ "_from": "tickets/12345", "_to": "resolutions/54321" }
{ "_from": "tickets/12346", "_to": "resolutions/54322" }
```

### What queries it enables
- "How was ticket #12345 fixed?" → Follow `resolved_with` → get resolution steps
- "Find similar ticket → get its resolution → suggest for new ticket" (the full RAG pipeline)

---

## Edge 8: `references`

### What it means
A resolution **was based on** a runbook.

### Why it exists
Links specific fixes back to documented procedures. Validates which runbooks are actually useful (if many resolutions reference KB-0001, that runbook is effective). Also helps the AI suggest: "Follow runbook KB-0001, which was successfully used to resolve 8 similar tickets."

### Diagram
```
┌──────────────┐      references        ┌──────────────┐
│ resolutions/ │ ────────────────────→  │ runbooks/    │
│ 54321        │                        │ KB-0001      │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A student's homework **references** a textbook chapter. If many students reference chapter 5, it's an important chapter.

### Example edges

```json
{ "_from": "resolutions/54321", "_to": "runbooks/KB-0001" }
{ "_from": "resolutions/54322", "_to": "runbooks/KB-0001" }
{ "_from": "resolutions/54323", "_to": "runbooks/KB-0003" }
```

### What queries it enables
- "Which runbook was used to fix ticket #12345?" → ticket → resolved_with → resolution → references → runbook
- "How many times has KB-0001 been used?" → Count `references` edges where `_to = runbooks/KB-0001`

---

## Edge 9: `triggered_by`

### What it means
A known error code **appeared in** a ticket.

### Why it exists
Pattern matching. When a ticket contains "FATAL: too many connections", the system matches it to ERR-PG-001, then follows `triggered_by` edges to find all past tickets with the same error → their resolutions. This is faster than embedding search for known errors.

### Diagram
```
┌──────────────┐     triggered_by       ┌──────────────┐
│ error_codes/ │ ────────────────────→  │ tickets/     │
│ ERR-PG-001   │                        │ 12345        │
└──────────────┘                        └──────────────┘
```

### Real-world analogy
A disease **was found in** a patient. Track all patients who had the same disease to see what treatments worked.

### Example edges

```json
{ "_from": "error_codes/ERR-PG-001", "_to": "tickets/12345" }
{ "_from": "error_codes/ERR-PG-001", "_to": "tickets/12350" }
{ "_from": "error_codes/ERR-NGINX-001", "_to": "tickets/12346" }
```

### What queries it enables
- "What past tickets had this same error?" → Find all `triggered_by` edges from ERR-PG-001
- "How often does ERR-PG-001 occur?" → Count edges from this error code
- "Is this error getting more frequent?" → Count edges by month

---

## Complete Edge Summary

```
engineers  ──member_of──>     teams
servers    ──managed_by──>    teams
servers    ──hosts──>         services
services   ──depends_on──>   services
tickets    ──affects──>       servers, services
tickets    ──assigned_to──>  teams
tickets    ──resolved_with──> resolutions
resolutions ──references──>  runbooks
error_codes ──triggered_by──> tickets
```

## Full Graph Traversal Example

A new ticket comes in: **"PostgreSQL not accepting connections on prod-db-01"**

```
Step 1: Extract entities from ticket text
   → "PostgreSQL" (service), "prod-db-01" (server)

Step 2: Look up in graph
   → servers/prod-db-01 ──hosts──> services/postgresql
   → servers/prod-db-01 ──managed_by──> teams/db-admin

Step 3: Find past tickets on this server
   → servers/prod-db-01 <──affects── tickets/042 (similar issue 2 months ago)

Step 4: Get the past resolution
   → tickets/042 ──resolved_with──> resolutions/015
   → resolutions/015: "Increased max_connections from 100 to 200"
   → resolutions/015 ──references──> runbooks/KB-0001

Step 5: Check error codes
   → "too many connections" matches error_codes/ERR-PG-001
   → error_codes/ERR-PG-001 ──triggered_by──> tickets/042, tickets/089

Step 6: Find expert
   → teams/db-admin <──member_of── engineers/Alex Chen (expertise: PostgreSQL)

Result:
   Category: Database (confidence: 0.95)
   Team: Database Admin
   Suggested resolution: Follow KB-0001, increase max_connections (worked before with 95% effectiveness)
   Recommended engineer: Alex Chen (resolved similar issue on this server)
```
