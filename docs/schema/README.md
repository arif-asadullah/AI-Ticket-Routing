# DeskMind Database Schema

This document explains the complete database schema for DeskMind — the AI-powered ticket routing system.

## What is ArangoDB?

ArangoDB is a database that supports three data models in one:
- **Documents** (like JSON objects — similar to MongoDB)
- **Graphs** (relationships between documents — nodes and edges)
- **Key-value** (fast lookups by ID)

We use all three. Tickets, teams, servers are **documents**. The relationships between them (which server runs which service, which team manages which server) are **edges** in a **graph**.

## Why a Graph Database?

Traditional databases store data in tables with rows and columns. To find "which team manages the server that runs PostgreSQL" you'd need multiple JOIN queries across 3 tables.

In a graph database, you just **traverse edges**:

```
PostgreSQL (service) ←── hosts ── prod-db-01 (server) ── managed_by ──→ Database Admin (team)
```

One query, follows the connections directly. This is what makes DeskMind's AI routing so powerful — it doesn't just match keywords, it **understands how your infrastructure is connected**.

## The Big Picture

```
                                    ┌──────────┐
                                    │  teams   │
                                    └────┬─────┘
                          member_of ↗    │ ↖ managed_by       ↖ assigned_to
                    ┌───────────┐        │      ┌──────────┐       ┌──────────┐
                    │ engineers │        │      │ servers  │       │ tickets  │
                    └───────────┘        │      └────┬─────┘       └──┬──┬───┘
                                         │      hosts↓          affects↓  │resolved_with
                                         │      ┌──────────┐             │
                                         │      │ services │       ┌─────┴──────┐
                                         │      └────┬─────┘       │resolutions │
                                         │   depends_on↓↑          └─────┬──────┘
                                         │                          references↓
                    ┌───────────────┐    │                        ┌──────────┐
                    │network_devices│    │                        │ runbooks │
                    └───────────────┘    │                        └──────────┘
                                         │
                    ┌──────────────┐     │     ┌───────────────┐
                    │ error_codes  │─triggered_by→│  tickets     │
                    └──────────────┘     │     └───────────────┘
                                         │
                                    ┌────┴──────────┐
                                    │ routing_rules │
                                    └───────────────┘
```

## Quick Reference

### Document Collections (12 total)

| Collection | What it stores | Example |
|-----------|---------------|---------|
| `tickets` | Support tickets submitted by users | "PostgreSQL not accepting connections" |
| `teams` | IT teams that handle tickets | "Database Admin" |
| `engineers` | Team members with expertise | "Alex Chen, Senior DBA" |
| `servers` | Infrastructure machines | "prod-db-01 (10.0.1.10, 32GB RAM)" |
| `services` | Software running on servers | "PostgreSQL 15.4, port 5432" |
| `network_devices` | Firewalls, switches, routers | "fw-prod-01 (Palo Alto)" |
| `error_codes` | Known error patterns | "FATAL: too many connections" |
| `runbooks` | Documented fix procedures | "How to handle PostgreSQL connection limit" |
| `resolutions` | Actual fixes applied to tickets | "Increased max_connections from 100 to 200" |
| `routing_rules` | Category-to-team mapping | "Database + high → db-admin" |
| `audit_log` | Action history for every ticket | "AI classified → routed → human overrode → resolved" |
| `category_centroids` | Average embedding per category | Used by centroid classifier to find closest category |

### Edge Collections (9 total)

| Edge | From → To | Meaning |
|------|-----------|---------|
| `hosts` | server → service | "prod-db-01 runs PostgreSQL" |
| `managed_by` | server → team | "prod-db-01 is managed by Database Admin" |
| `depends_on` | service → service | "OrderService depends on PostgreSQL" |
| `member_of` | engineer → team | "Alex Chen is on Database Admin team" |
| `affects` | ticket → server/service | "This ticket is about prod-db-01" |
| `assigned_to` | ticket → team | "This ticket was sent to Database Admin" |
| `resolved_with` | ticket → resolution | "This ticket was fixed by increasing max_connections" |
| `references` | resolution → runbook | "This fix followed runbook KB-0001" |
| `triggered_by` | error_code → ticket | "Error ERR-PG-001 appeared in this ticket" |

### Indexes

| Type | Collection | Fields | Purpose |
|------|-----------|--------|---------|
| Persistent | tickets | category, priority, status | Fast filtering |
| Full-text | tickets | title, description | Keyword search |
| Vector (384-dim) | tickets | embedding | Find similar tickets by meaning |
| Vector (384-dim) | runbooks | embedding | Find relevant runbooks |
| Vector (384-dim) | resolutions | embedding | Find similar past fixes |
| Persistent | routing_rules | category, priority | Fast rule lookup |
| Persistent | audit_log | ticket_id | Find all actions for a ticket |
| Persistent | audit_log | created_at | Time-ordered audit trail |

### 6 Ticket Categories

| Category | Domain | Team |
|----------|--------|------|
| Infrastructure | Servers, VMs, OS, hardware | Infrastructure Ops |
| Application | Apps, APIs, deployments, bugs | Application Support |
| Security | Auth, encryption, vulnerabilities | Security Ops |
| Database | SQL, connections, replication | Database Admin |
| Storage | Disk, NFS, SAN, backups | Storage Ops |
| Network | DNS, firewall, VPN, latency | Network Engineering |

## Where are Vectors (Embeddings) Stored?

Vectors are stored **inside the same document** in ArangoDB — not in a separate vector database.

### What is a vector/embedding?

When you write a sentence like *"PostgreSQL not accepting connections"*, the AI model (MiniLM) converts it into a list of 384 numbers:

```
"PostgreSQL not accepting connections"  →  [0.012, -0.034, 0.089, ... 381 more numbers]
```

These numbers represent the **meaning** of the text. Two sentences that mean the same thing (even with different words) will have similar numbers:

```
"PostgreSQL not accepting connections"  →  [0.82, -0.15, 0.33, ...]
"Database refusing new connections"     →  [0.80, -0.14, 0.35, ...]  ← very similar!
"NGINX returning 502 errors"           →  [0.11, 0.67, -0.22, ...]  ← very different
```

### Where exactly they're stored:

The `embedding` field sits right next to the other fields in the same document:

```json
{
  "_key": "12345",
  "title": "PostgreSQL not accepting connections",
  "description": "prod-db-01 refusing connections...",
  "category": "Database",
  "priority": "high",
  "embedding": [0.012, -0.034, 0.089, ... 381 more numbers]
}
```

### Which collections have embeddings:

| Collection | What gets embedded | Why |
|-----------|-------------------|-----|
| `tickets` | Ticket description | Find similar past tickets by meaning |
| `runbooks` | Runbook title + steps | Find the most relevant guide for a new ticket |
| `resolutions` | Resolution steps | Find similar past fixes to suggest |

### How similarity search works:

```
New ticket: "Redis memory full on prod-app-01"
                    ↓
MiniLM converts to embedding: [0.45, -0.23, 0.67, ...]
                    ↓
ArangoDB vector index compares against all ticket embeddings
                    ↓
Results (most similar first):
  1. "Redis OOM on prod-app-01"           — 0.94 similarity ← best match
  2. "Memory exhaustion on cache server"  — 0.89 similarity
  3. "PostgreSQL out of memory"           — 0.72 similarity
```

### Why NOT a separate vector database (Pinecone, Weaviate, etc.)?

| Separate vector DB | ArangoDB (our approach) |
|-------------------|------------------------|
| Need 2 databases to maintain | Everything in 1 database |
| Must keep IDs in sync between DB and vector store | No sync — same document |
| Extra cost and infrastructure | One service |
| Can't combine vector search with graph traversal | Vector + graph in one query |

ArangoDB 3.12 supports vectors natively — we get **graph + vectors + documents** all in one place. This is the key advantage.

### When are embeddings created?

| Event | What happens |
|-------|-------------|
| Seed data loaded (`seed_db.py`) | MiniLM computes embeddings for all 50 seed tickets + runbooks + resolutions |
| New ticket submitted | Backend computes embedding before saving to ArangoDB |
| New resolution created | Backend computes embedding before saving |

The embedding is computed once when the document is created. It doesn't change unless the text changes.

### The vector index

A vector index is created on the `embedding` field to make similarity search fast:

- **Without index**: Compare the new ticket to ALL 10,000 tickets one by one → slow
- **With index**: Uses HNSW algorithm to find the 5 most similar tickets in milliseconds → fast

The index is created once during database initialization. ArangoDB maintains it automatically.

---

## How Everything Works Together (The Full Picture)

When a user submits a ticket, here's what DeskMind does:

```
Step 1: USER SUBMITS TICKET
   "PostgreSQL not accepting connections on prod-db-01"
         ↓
Step 2: COMPUTE EMBEDDING
   MiniLM converts description → [0.82, -0.15, 0.33, ...]
         ↓
Step 3: VECTOR SEARCH (find similar past tickets)
   Search embedding in tickets collection
   → Found: TKT-042 "PostgreSQL max_connections reached" (0.94 similarity)
         ↓
Step 4: GRAPH TRAVERSAL (find context)
   prod-db-01 ──hosts──→ PostgreSQL ──managed_by──→ Database Admin
   TKT-042 ──resolved_with──→ RES-015 ──references──→ KB-0001
   teams/db-admin ←──member_of── Alex Chen (PostgreSQL expert)
         ↓
Step 5: LLM CLASSIFICATION
   Phi-3-mini reads ticket + graph context
   → category: "Database", priority: "high", confidence: 0.95
         ↓
Step 6: ROUTING RULE LOOKUP
   routing_rules: Database + high → db-admin
         ↓
Step 7: ROUTE TICKET
   Ticket assigned to Database Admin team
   Status: "routed"
   AI reasoning: "PostgreSQL connection issue on production database server"
   Suggested fix: KB-0001 (Increase max_connections)
   Recommended engineer: Alex Chen
```

This is why we need all 10 collections, 9 edges, and 3 types of indexes working together. Each piece plays a role in making the routing intelligent.

---

## Detailed Documentation

- [collections.md](collections.md) — All 12 document collections explained field-by-field
- [edges.md](edges.md) — All 9 edge collections with examples
- [indexes.md](indexes.md) — Index types and why each is needed
- [graph.md](graph.md) — Graph definition + real query examples
