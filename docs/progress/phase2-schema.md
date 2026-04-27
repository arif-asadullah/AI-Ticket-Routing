# Phase 2: Database Schema

## What We Did

Designed and implemented the complete ArangoDB schema — 12 document collections, 9 edge collections, 1 named graph, and all indexes including vector search.

## Why We Need a Schema

Without a schema, the database is just an empty box. The schema defines:
- **What data we store** (tickets, servers, teams, etc.)
- **How data is connected** (which server runs which service, who manages what)
- **How to search fast** (indexes for filtering, full-text search, and vector similarity)

## What Was Created

### 12 Document Collections

| Collection | What it stores | Count |
|-----------|---------------|-------|
| `tickets` | Support tickets (user-submitted + seed + synthetic) | 855 |
| `teams` | 6 IT teams (Infrastructure Ops, Database Admin, etc.) | 6 |
| `engineers` | Team members with expertise | 12 |
| `servers` | Infrastructure machines (prod-db-01, etc.) | 15 |
| `services` | Software services (PostgreSQL, Redis, etc.) | 12 |
| `network_devices` | Firewalls, switches, load balancers | 5 |
| `error_codes` | Known error patterns (20 patterns) | 20 |
| `runbooks` | Documented fix procedures | 10 |
| `resolutions` | Actual fixes applied to tickets | 830 |
| `routing_rules` | Category → team mapping (6 categories x 4 priorities) | 24 |
| `audit_log` | Action history for every ticket | grows |
| `category_centroids` | Average embedding per category (for centroid classifier) | 6 |

### 9 Edge Collections

| Edge | From → To | What it means |
|------|-----------|--------------|
| `hosts` | server → service | "prod-db-01 runs PostgreSQL" |
| `managed_by` | server → team | "prod-db-01 managed by Database Admin" |
| `depends_on` | service → service | "OrderService depends on PostgreSQL" |
| `member_of` | engineer → team | "Arjun Nair is on Database Admin" |
| `affects` | ticket → server/service | "This ticket is about prod-db-01" |
| `assigned_to` | ticket → team | "Ticket routed to Database Admin" |
| `resolved_with` | ticket → resolution | "Ticket fixed by increasing max_connections" |
| `references` | resolution → runbook | "Resolution followed KB-0001" |
| `triggered_by` | error_code → ticket | "ERR-PG-001 appeared in this ticket" |

### Indexes

| Type | Collection | Purpose |
|------|-----------|---------|
| Persistent | tickets (category, priority, status, created_at) | Fast filtering |
| Full-text | tickets (title, description) | Keyword search |
| Vector (384-dim) | tickets, runbooks, resolutions | Similarity search by meaning |
| Persistent | routing_rules (category, priority) | Fast rule lookup |
| Persistent | audit_log (ticket_id, created_at) | Audit trail |

### Named Graph: `deskmind_graph`

All edge collections tied together into one graph that can be traversed with AQL queries.

## How Schema is Created

The schema is created **automatically** when the backend starts — no manual steps.

**File**: `backend/services/schema.py`

The `init_schema(db)` function:
1. Creates all 12 document collections (skips if they exist)
2. Creates all 9 edge collections
3. Creates the named graph with edge definitions
4. Creates all indexes (persistent, full-text, vector)
5. Vector indexes retry up to 5 times (ArangoDB needs ~10 seconds to initialize vector subsystem)

Called from `backend/app/main.py` lifespan on every startup. Idempotent — safe to run multiple times.

## 6 Ticket Categories

| Category | What it covers | Team |
|----------|---------------|------|
| Infrastructure | Servers, VMs, OS, CPU, RAM, hardware | Infrastructure Ops |
| Application | App crashes, API errors, deployments, bugs | Application Support |
| Database | SQL, connections, replication, backups | Database Admin |
| Network | Firewalls, DNS, VPN, latency, certificates | Network Engineering |
| Security | Auth, vulnerabilities, access control | Security Ops |
| Storage | NFS, SAN, disk I/O, RAID, backups | Storage Ops |

## Documentation

Detailed field-by-field docs in `docs/schema/`:
- `collections.md` — every field of every collection explained
- `edges.md` — every edge with diagrams and examples
- `indexes.md` — all index types explained
- `graph.md` — graph definition + 8 real AQL query examples
