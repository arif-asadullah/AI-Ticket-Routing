# DeskMind — Low Level Design Document

> **Nasscom AI-Code-Sarathi Excel Hackathon — Final Round (Jury)**
> **Team**: Arif Asadullah, Aakarsh, Mohit Tomar
> **Date**: June 2026 (updated from R2 submission)

---

## 1. Module Dependency Diagram

```
                              ┌────────────────────────────┐
                              │      app/main.py           │
                              │  (FastAPI lifespan entry)   │
                              └────────┬───────────────────┘
                                       │
                          ┌────────────┼─────────────┐
                          │            │             │
                          ▼            ▼             ▼
                   ┌──────────┐ ┌──────────┐ ┌──────────────┐
                   │ database │ │  cache   │ │   schema     │
                   │  .py     │ │  .py     │ │   .py        │
                   └──────────┘ └──────────┘ └──────────────┘
                          │            │             │
                          └────────────┼─────────────┘
                                       │
                              ┌────────▼───────────────────────┐
                              │        api/router.py              │
                              │  ┌──────┬──────┬──────┬──────┐   │
                              │  │ auth │tickets│health│ chat │   │
                              │  └──┬───┘──┬───┘└─────┘└─────┘   │
                              └─────┼──────┼──────────────────────┘
                                    │      │
                          ┌─────────┘      └──────────┐
                          ▼                           ▼
               ┌─────────────────────┐   ┌─────────────────────────────────────┐
               │   core/auth.py      │   │       orchestrator.py                │
               │                     │   │  classify() — Pipeline controller    │
               │ - hash_password()   │   └──────┬────────┬──────────┬─────┬────┘
               │ - verify_password() │          │        │          │     │
               │ - create_*_token()  │ ┌────────┘   ┌────┘     ┌───┘  ┌──┘
               │ - decode_token()    │ ▼            ▼          ▼      ▼
               │ - get_current_user()│ ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────┐
               │ - require_role()    │ │ Stage 1: │ │Stage 2:│ │Stg 3:│ │Stage 4:│
               │ - require_team_    │ │ PREPARE  │ │RETRIEVE│ │CLASS.│ │AGGREG. │
               │   access()         │ └──────────┘ └────────┘ └──────┘ └────────┘
               └─────────────────────┘
                         │        │          │         │
              ┌──────────┘   ┌────┘     ┌────┘    ┌────┘
              ▼              ▼          ▼         ▼
    ┌──────────────┐  ┌──────────┐ ┌────────┐ ┌──────────┐
    │  Stage 1:    │  │ Stage 2: │ │Stage 3:│ │ Stage 4: │
    │  PREPARE     │  │ RETRIEVE │ │CLASSIFY│ │AGGREGATE │
    │              │  │          │ │        │ │          │
    │-entity_      │  │-retrieval│ │-llm_   │ │-aggregat │
    │ extractor.py │  │ .py      │ │ class. │ │ or.py    │
    │-error_       │  │          │ │-knn_   │ │-error_   │
    │ scanner.py   │  │          │ │ class. │ │ scanner  │
    │-quality_     │  │          │ │-centro │ │ .py      │
    │ scorer.py    │  │          │ │ id_cl. │ │          │
    │-SentenceTr.  │  │          │ │-keywor │ │          │
    │ (embedding)  │  │          │ │ d_cl.  │ │          │
    └──────┬───────┘  └──────────┘ └────────┘ └──────────┘
           │
           ▼
    ┌──────────────┐
    │ core/        │
    │ config.py    │   ← Settings singleton (env vars)
    └──────────────┘

Call graph (function-level):

  api.tickets.create_ticket()
      │
      ├── orchestrator.classify(title, description, db, redis_client)
      │       │
      │       ├── check_health(db, redis_client)           → HealthStatus
      │       ├── entity_extractor.extract(description)    → ExtractedEntities
      │       ├── score_quality(title, description, ents)  → "HIGH"|"MEDIUM"|"LOW"
      │       ├── model.encode(description)                → list[float] (384-dim)
      │       │
      │       ├── retrieve_all(db, embedding, entities, description)
      │       │       ├── search_similar_tickets(db, embedding)
      │       │       ├── search_by_error_codes(db, error_codes)
      │       │       ├── traverse_graph(db, entities)
      │       │       └── search_fulltext(db, description)
      │       │
      │       ├── classify_llm(title, description, context)
      │       ├── classify_knn(similar_tickets)
      │       ├── classify_centroid(embedding, db)
      │       ├── classify_keyword(description)
      │       │
      │       ├── aggregate(votes, quality, errors, graph_confirms)
      │       │
      │       ├── lookup_team(db, category, priority)
      │       ├── find_runbook(db, category, title, description)
      │       └── [resolution selection from 3 sources]
      │
      ├── db.collection("tickets").insert({
      │       title, description, category, secondary_category,
      │       priority, status, confidence_score, ai_reasoning,
      │       quality_score, classifier_votes, submitted_by, routed_to,
      │       embedding, suggested_resolution, resolution_effectiveness,
      │       suggested_runbook, recommended_expert, created_at, _source: "user"
      │   })
      ├── db.collection("assigned_to").insert(...)
      └── db.collection("audit_log").insert(...)

  api.auth.login()
      │
      ├── db.aql.execute("FOR u IN users FILTER u.email == @email ...")
      ├── auth.verify_password(plain, user.password_hash)   → bool
      ├── auth.create_access_token({sub, role, team_key})   → JWT (30 min)
      └── auth.create_refresh_token({sub, role, team_key})  → JWT (7 days)

  api.auth.register()  [requires: Depends(require_admin)]
      │
      ├── db.collection("engineers").get(engineer_key)      → validate engineer exists
      ├── db.aql.execute("... member_of ...")               → resolve team_key from graph
      ├── auth.hash_password(plain)                         → bcrypt hash
      └── db.collection("users").insert({email, hash, role, team_key, ...})

  [Every protected endpoint]
      │
      ├── auth.get_current_user(request, credentials)
      │       ├── auth.decode_token(bearer_token)           → {sub, role, team_key, type}
      │       └── db.aql.execute("FOR u IN users ...")      → validate user active
      │
      └── auth.require_team_access(ticket.routed_to, user, db)  [inline, for ticket mutations]
              ├── admin → bypass
              ├── user → 403
              └── engineer → db.collection("teams").get(team_key) → compare name
```

---

## 2. Data Structures

### 2.1 Pydantic Models (API Layer)

```python
# backend/schemas/ticket.py

class TicketCreate(BaseModel):
    title: str                          # Ticket title / subject line
    description: str                    # Full ticket description text
    priority: str = "medium"            # "critical" | "high" | "medium" | "low"
    submitted_by: str | None = None     # Engineer email or name

class TicketStatusUpdate(BaseModel):
    status: str                         # "in_progress" | "escalated" | "routed"
    assigned_to: str | None = None      # Team name (for manual reassignment)
    updated_by: str | None = None       # Engineer email

class TicketResolve(BaseModel):
    resolution_steps: list[str]         # What was done to fix it
    used_ai_suggestion: str = "no"      # "yes" | "partially" | "no"
    used_runbook: str | None = None     # "KB-0001" or null
    resolved_by: str | None = None      # Engineer email

class TicketFeedback(BaseModel):
    rating: str                         # "helpful" | "not_helpful"
    comment: str | None = None          # Optional free-text comment

class TicketResponse(BaseModel):
    id: str                                         # ArangoDB _key
    title: str
    description: str
    category: str | None = None                     # "Infrastructure" | "Application" | ... (6 values)
    secondary_category: str | None = None           # Runner-up category if score > 0.15
    priority: str                                   # "critical" | "high" | "medium" | "low"
    status: str                                     # "routed" | "escalated" | "in_progress" | "resolved" | "closed"
    confidence_score: float | None = None           # 0.0 - 0.99 (capped by quality)
    ai_reasoning: str | None = None                 # LLM explanation of classification
    quality_score: str | None = None                # "HIGH" | "MEDIUM" | "LOW"
    classifier_votes: dict | None = None            # Full vote breakdown from all 4 classifiers
    submitted_by: str | None = None
    routed_to: str | None = None                    # Team name
    suggested_resolution: list[str] | None = None   # Steps to resolve (from past tickets)
    resolution_effectiveness: float | None = None   # 0.0 - 1.0
    suggested_runbook: str | None = None            # "KB-0001: Restart PostgreSQL"
    recommended_expert: str | None = None           # Best engineer for this issue
    picked_up_by: str | None = None                 # Email of engineer who picked up the ticket
    created_at: str | None = None                   # ISO 8601 UTC timestamp
    resolved_at: str | None = None                  # ISO 8601 UTC timestamp
```

### 2.2 TypedDicts (Pipeline Internal)

```python
# backend/services/orchestrator.py

class ClassificationResult(TypedDict):
    category: str | None                        # Winning category
    secondary_category: str | None              # Runner-up (if score > 0.15)
    priority: str                               # "critical" | "high" | "medium" | "low"
    confidence: float                           # Final confidence after scenario + quality caps (0.0 - cap)
    agreement: str                              # "4/4", "3/4", "2/4", etc.
    quality_score: str                          # "HIGH" | "MEDIUM" | "LOW"
    classifier_votes: dict                      # Raw votes from each classifier
    reasoning: str                              # LLM reasoning string
    degradation_level: int                      # 1-4 (health status)
    embedding: list[float] | None               # 384-dim MiniLM vector
    suggested_resolution: list[str] | None      # Steps from best matching past ticket
    resolution_effectiveness: float | None      # 0.0 - 1.0
    suggested_runbook: str | None               # "KB-0001: Title"
    recommended_team: str | None                # Team name from routing_rules
    recommended_expert: str | None              # Engineer name from graph
    processing_time_ms: int                     # End-to-end pipeline time

class HealthStatus(TypedDict):
    ollama: bool                # Ollama reachable
    db_has_data: bool           # ArangoDB has tickets
    redis: bool                 # Redis reachable
    level: int                  # 1 (emergency) to 4 (full)
```

```python
# backend/services/retrieval.py

class SimilarTicket(TypedDict):
    key: str                                # ArangoDB _key
    title: str                              # Ticket title
    category: str                           # Category of past ticket
    priority: str                           # Priority of past ticket
    description: str                        # First 200 chars of description
    similarity: float                       # Cosine similarity score (0.0 - 1.0)
    resolution_steps: list[str] | None      # Steps from resolved_with edge

class GraphContext(TypedDict):
    server_type: str | None                 # "web-server", "db-server", etc.
    server_datacenter: str | None           # "DC-East", "DC-West"
    managed_by_team: str | None             # Team name
    managed_by_domain: str | None           # Team domain category
    hosted_services: list[str]              # Services running on server
    dependent_services: list[str]           # Services depending on matched services
    past_tickets_on_server: list[dict]      # Recent closed tickets on same server
    experts: list[dict]                     # Team members: {name, role, expertise}

class RetrievalResult(TypedDict):
    similar_tickets: list[SimilarTicket]    # Vector search results (top 5)
    error_matched_tickets: list[dict]       # Error code graph traversal results
    graph_context: GraphContext | None       # Infrastructure context
    fulltext_matches: list[dict]            # Fulltext index search results
```

```python
# backend/services/entity_extractor.py

class ExtractedEntities(TypedDict):
    servers: list[str]          # Matched server _keys (e.g., ["web-prod-01"])
    services: list[str]         # Matched service _keys (e.g., ["postgresql-main"])
    error_codes: list[dict]     # Matched errors: [{error_key, pattern, service, severity}]
```

```python
# backend/services/error_scanner.py

class ErrorMatch(TypedDict):
    error_key: str      # ArangoDB _key (e.g., "ERR-PG-001")
    pattern: str        # Matched text pattern (e.g., "FATAL: connection refused")
    service: str        # Associated service (e.g., "postgresql")
    severity: str       # "critical" | "high" | "medium" | "low"
```

### 2.3 Configuration Model

```python
# backend/core/config.py

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    ARANGO_URL: str = "http://localhost:8529"
    ARANGO_DB: str = "ticket_agent"
    ARANGO_USER: str = "root"
    ARANGO_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CONFIDENCE_THRESHOLD: float = Field(default=0.70, ge=0.0, le=1.0)
    LOG_LEVEL: str = "INFO"
```

---

## 3. Module-Level Breakdown

### 3.1 `app/main.py` — Application Entry Point

| Function | Signature | Description |
|----------|-----------|-------------|
| `lifespan` | `async def lifespan(app: FastAPI)` | Async context manager for startup/shutdown. Connects ArangoDB, Redis; initializes schema. |

**Startup sequence**: `connect_arango()` -> `connect_redis()` -> `init_schema(db)` -> yield -> `close_arango()` -> `close_redis()`

### 3.2 `services/database.py` — ArangoDB Connection

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `_is_port_open` | `(url: str, timeout: float = 2.0) -> bool` | `bool` | TCP port check before connection attempt |
| `connect_arango` | `() -> StandardDatabase \| None` | `StandardDatabase \| None` | Connect to ArangoDB, create database if missing, return handle |
| `close_arango` | `() -> None` | `None` | Close client connection |

### 3.3 `services/cache.py` — Redis Connection

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `connect_redis` | `async () -> aioredis.Redis \| None` | `Redis \| None` | Connect to Redis with `decode_responses=True` |
| `close_redis` | `async () -> None` | `None` | Close Redis connection |

### 3.4 `services/schema.py` — ArangoDB Schema Initialization

| Function | Signature | Description |
|----------|-----------|-------------|
| `init_schema` | `(db: StandardDatabase) -> None` | Idempotent: creates 15 doc collections, 9 edge collections, 1 named graph, all indexes |
| `_create_indexes` | `(db: StandardDatabase) -> None` | Creates persistent, fulltext, vector, and unique indexes with retry logic |

### 3.5 `services/orchestrator.py` — Classification Pipeline Controller

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `check_health` | `async (db, redis_client) -> HealthStatus` | `HealthStatus` | Cached (5s TTL) health check for Ollama, ArangoDB, Redis |
| `get_embedding_model` | `() -> SentenceTransformer` | `SentenceTransformer` | Singleton loader for `all-MiniLM-L6-v2` |
| `classify` | `async (title, description, db, redis_client) -> ClassificationResult` | `ClassificationResult` | Full 5-stage pipeline execution |
| `find_runbook` | `(db, category, title, description) -> str \| None` | `str \| None` | AQL lookup of runbook by category, relevance-gated by title-word overlap with the ticket text |
| `lookup_team` | `(db, category, priority) -> str \| None` | `str \| None` | AQL lookup of team via routing_rules join |

### 3.6 `services/entity_extractor.py` — Entity Extraction

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `EntityExtractor.__init__` | `(self)` | | Initialize empty caches |
| `EntityExtractor.refresh_cache` | `(self, db) -> None` | `None` | Load server keys, service keys+names, error patterns from ArangoDB (5-min TTL) |
| `EntityExtractor.extract` | `(self, text, db) -> ExtractedEntities` | `ExtractedEntities` | Case-insensitive substring matching of servers, services, error patterns |

### 3.7 `services/error_scanner.py` — Error Code Analysis

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `scan_errors` | `(text, db) -> list[ErrorMatch]` | `list[ErrorMatch]` | Delegates to `entity_extractor.extract()` for error code matching |
| `get_highest_severity` | `(errors) -> str \| None` | `str \| None` | Returns max severity from matched errors |
| `errors_confirm_category` | `(errors, category) -> bool` | `bool` | Maps error service to category and checks if it confirms the classification |

### 3.8 `services/quality_scorer.py` — Input Quality Assessment

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `score_quality` | `(title, description, entities) -> str` | `"HIGH" \| "MEDIUM" \| "LOW"` | Score based on description length (>50 chars) and entity presence |
| `get_confidence_cap` | `(quality_score) -> float` | `float` | HIGH=0.99, MEDIUM=0.85, LOW=0.69 — LOW is intentionally kept below the 0.70 auto-route threshold so low-quality/vague tickets always escalate to human review. (`quality_scorer.py` still carries a stale local 0.75 that should be reconciled to 0.69; the aggregator's `QUALITY_CAPS` LOW=0.69 is what gates routed confidence.) |

### 3.9 `services/retrieval.py` — Hybrid Retrieval (4 methods)

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `search_similar_tickets` | `(db, embedding, limit=5) -> list[SimilarTicket]` | `list[SimilarTicket]` | AQL COSINE_SIMILARITY on ticket embeddings |
| `search_by_error_codes` | `(db, error_codes) -> list[dict]` | `list[dict]` | Graph traversal via `triggered_by` edges, deduplicated |
| `traverse_graph` | `(db, entities) -> GraphContext \| None` | `GraphContext \| None` | Multi-hop AQL: server -> hosts -> managed_by -> affects -> member_of |
| `search_fulltext` | `(db, text, limit=5) -> list[dict]` | `list[dict]` | ArangoDB FULLTEXT() on description, top 5 keywords, deduplicated |
| `retrieve_all` | `(db, embedding, entities, description) -> RetrievalResult` | `RetrievalResult` | Runs all 4 methods and combines results |

### 3.10 `services/llm_classifier.py` — LLM Classifier (weight: 0.40)

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `_build_context_section` | `(context: RetrievalResult) -> str` | `str` | Formats graph, similar tickets, error matches into prompt text |
| `_parse_llm_response` | `(text: str) -> dict` | `dict` | Extracts JSON from LLM output, handles markdown code blocks |
| `classify_llm` | `async (title, description, context) -> dict` | `dict` | Sends to Ollama, validates category/priority/confidence |

### 3.11 `services/knn_classifier.py` — KNN Classifier (weight: 0.15)

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `classify_knn` | `(similar_tickets, k=5) -> dict` | `dict` | Similarity-weighted voting on top K neighbors |

### 3.12 `services/centroid_classifier.py` — Centroid Classifier (weight: 0.30)

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `_cosine_similarity` | `(a, b) -> float` | `float` | NumPy-based cosine similarity |
| `_load_centroids` | `(db) -> list[dict]` | `list[dict]` | Loads category_centroids from ArangoDB (1-hour in-memory cache) |
| `classify_centroid` | `(embedding, db) -> dict` | `dict` | Compares embedding to 6 centroids, returns closest with gap-based confidence |

### 3.13 `services/keyword_classifier.py` — Keyword Classifier (weight: 0.15)

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `classify_keyword` | `(text: str) -> dict` | `dict` | Counts keyword hits across 6 category dictionaries (25+ keywords each) |

### 3.14 `services/aggregator.py` — Majority-Aware Aggregator

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `aggregate` | `(votes, quality_score, error_codes, graph_confirms_category) -> dict` | `dict` | 6-phase majority-aware voting; selection sets a SCENARIO_CAP, then confidence = 0.60·supporter_avg_conf + 0.25·vote_share + 0.15·weight_share (+0.03 error, +0.02 graph), capped by scenario + quality |
| `_get_weights` | `(active_votes) -> dict` | `dict` | Returns appropriate weight set based on which classifiers are active |

### 3.15 `api/tickets.py` — Ticket API Endpoints (all protected)

| Endpoint | Function | Auth Guard | Description |
|----------|----------|-----------|-------------|
| `GET /api/tickets` | `list_tickets` | `get_current_user` | List tickets — engineers see own team only |
| `POST /api/tickets` | `create_ticket` | `require_any_authenticated` | Create + classify + route (submitted_by = user email) |
| `GET /api/tickets/{id}` | `get_ticket` | `get_current_user` | Get ticket — engineers only if routed to their team |
| `PATCH /api/tickets/{id}/status` | `update_ticket_status` | `require_engineer_or_admin` + `require_team_access` | Engineer picks up / reassigns / escalates. Sets `picked_up_by` to engineer email on `in_progress`; clears it on `escalated`/`routed`. Returns 409 if ticket is already picked up by another engineer. |
| `POST /api/tickets/{id}/resolve` | `resolve_ticket` | `require_engineer_or_admin` + `require_team_access` | Resolve ticket (team-scoped). Only the engineer who picked up the ticket (or admin) can resolve it — 403 otherwise. |
| `POST /api/tickets/{id}/feedback` | `submit_feedback` | `get_current_user` | Rate AI suggestion as "helpful" or "not_helpful" with optional comment. Logged to `audit_log`. |
| `DELETE /api/tickets/{id}` | `delete_ticket` | `require_admin` | Admin only |

### 3.16 `core/auth.py` — Authentication & Authorization

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `hash_password` | `(plain: str) -> str` | `str` | Bcrypt hash using passlib |
| `verify_password` | `(plain: str, hashed: str) -> bool` | `bool` | Verify plaintext against bcrypt hash |
| `create_access_token` | `(data: dict) -> str` | `str` | JWT with 30-min expiry, type="access" |
| `create_refresh_token` | `(data: dict) -> str` | `str` | JWT with 7-day expiry, type="refresh" |
| `decode_token` | `(token: str) -> dict` | `dict` | Decode + validate JWT signature and expiry |
| `get_current_user` | `async (request, credentials) -> dict` | `dict` | FastAPI dependency — extract user from Bearer token, verify in DB |
| `require_role` | `(*allowed_roles) -> Depends` | `dict` | Factory — returns dependency checking user role |
| `require_team_access` | `async (ticket_routed_to, user, db) -> bool` | `bool` | Inline check — engineer must belong to ticket's team |

### 3.17 `api/auth.py` — Auth API Endpoints

| Endpoint | Function | Auth | Description |
|----------|----------|------|-------------|
| `POST /api/auth/bootstrap` | `bootstrap` | Public (only when 0 users) | Create first admin account |
| `POST /api/auth/login` | `login` | Public | Email + password → access + refresh JWT tokens |
| `POST /api/auth/register` | `register` | Admin only | Create new user linked to engineer/team |
| `POST /api/auth/refresh` | `refresh` | Public (needs refresh token) | Exchange refresh token for new tokens |
| `GET /api/auth/me` | `me` | Any authenticated | Current user info with team name |
| `GET /api/auth/users` | `list_users` | Admin only | List all user accounts |
| `PATCH /api/auth/users/{email}/toggle-active` | `toggle_user_active` | Admin only | Activate/deactivate user |
| `GET /api/auth/engineers` | `list_engineers` | Admin only | List engineers with team info (for user creation form) |

### 3.18 `api/stats.py` — Stats & Timeline API Endpoints

| Endpoint | Function | Auth Guard | Description |
|----------|----------|-----------|-------------|
| `GET /api/stats` | `get_stats` | `get_current_user` | Aggregated metrics — admin sees global stats, engineer sees team-scoped. Cached in Redis (60s TTL). Returns: total tickets, by_category, by_status, by_priority, avg_confidence, confidence_by_category, escalation_rate, avg_resolution_minutes, daily_trend, top_teams, feedback (helpful/not_helpful counts), classifier_agreement. |
| `GET /api/stats/tickets/{id}/timeline` | `get_ticket_timeline` | `get_current_user` | Audit trail for a specific ticket. Returns all `audit_log` entries for the ticket sorted by `created_at` ASC. Engineers can only view timelines for their team's tickets. |

### 3.19 `schemas/auth.py` — Auth Pydantic Models

| Model | Fields | Description |
|-------|--------|-------------|
| `UserRegister` | email, password, role, engineer_key | Admin creates a new user |
| `UserLogin` | email, password | Login request |
| `TokenResponse` | access_token, refresh_token, token_type | Login/refresh response |
| `TokenRefreshRequest` | refresh_token | Refresh request |
| `UserResponse` | email, role, team_key, team_name, engineer_key, is_active | User info response |

### 3.20 Frontend Components — File Summary

| Component | File | Purpose |
|-----------|------|---------|
| `DomainDashboard` | `frontend/src/components/DomainDashboard.jsx` | Main ticket queue view. Grouped by 6 IT domains (Infrastructure, Application, Database, Network, Security, Access Management). Contains ticket creation form, filtering, and embeds `StatsSummaryBar` and `TicketDetail`. |
| `TicketDetail` | `frontend/src/components/TicketDetail.jsx` | Expanded ticket view with full classification details, status actions (pick up, escalate, reassign), and embeds `ResolveForm`, `FeedbackWidget`, and `AuditTimeline`. |
| `ResolveForm` | `frontend/src/components/ResolveForm.jsx` | Resolution form. Pre-fills resolution steps from `ticket.suggested_resolution` when available. Engineer indicates AI suggestion usage (yes/partially/no) and runbook reference. |
| `FeedbackWidget` | `frontend/src/components/FeedbackWidget.jsx` | Inline widget to rate AI classification/resolution suggestion as helpful or not_helpful with an optional comment. Calls `POST /api/tickets/{id}/feedback`. |
| `AnalyticsDashboard` | `frontend/src/components/AnalyticsDashboard.jsx` | Full analytics page built with Recharts. Includes category distribution bar chart, status donut chart, priority breakdown, daily ticket trend area chart, top teams, feedback (helpful vs not_helpful), and classifier agreement rate. |
| `AuditTimeline` | `frontend/src/components/AuditTimeline.jsx` | Visual audit trail for a ticket. Displays classified, routed, escalated, in_progress, resolved, feedback, and closed events with timestamps, actors, and confidence signals. Calls `GET /api/stats/tickets/{id}/timeline`. |
| `StatsSummaryBar` | `frontend/src/components/StatsSummaryBar.jsx` | Animated counter bar showing total tickets, average confidence, escalation rate, and average resolution time. Uses animated value hooks for smooth number transitions. Calls `GET /api/stats`. |

---

## 4. Classification Pipeline — Detailed Stage-by-Stage Flow

### Stage 1: PREPARE

| Step | Operation | Input | Output | Latency |
|------|-----------|-------|--------|---------|
| 1a | Entity Extraction | `description` (str), ArangoDB cache | `ExtractedEntities` {servers, services, error_codes} | ~2ms (cache hit) |
| 1b | Quality Scoring | `title`, `description`, `ExtractedEntities` | `"HIGH"` / `"MEDIUM"` / `"LOW"` | <1ms |
| 1c | Embedding Generation | `description` (str) | `list[float]` (384-dim vector) | ~50-200ms |

### Stage 2: RETRIEVE (4 parallel searches)

| Step | Operation | Input | Output | Latency |
|------|-----------|-------|--------|---------|
| 2a | Vector Similarity Search | 384-dim embedding | Top 5 `SimilarTicket` with cosine similarity + resolution_steps | ~20-50ms |
| 2b | Error Code Traversal | `error_codes` list | Past tickets with same errors via `triggered_by` edges | ~10-30ms |
| 2c | Graph Traversal | `entities.servers[0]` | `GraphContext` (team, services, past tickets, experts) | ~30-80ms |
| 2d | Fulltext Search | Top 5 keywords from description | Matching past tickets from FULLTEXT() index | ~10-30ms |

### Stage 3: CLASSIFY (4 classifiers in parallel via `asyncio.gather()`)

All 4 classifiers run concurrently. Total time = LLM time (~2s), not the sum of all 4.

| Step | Classifier | Input | Output | Latency |
|------|-----------|-------|--------|---------|
| 3a | LLM (Qwen 2.5:7B) | title + description + full Stage 2 context + 12 disambiguation rules + 6 few-shot examples | {category, priority, confidence, reasoning} | ~5,000-7,000ms |
| 3b | KNN Voting | `context.similar_tickets` (top 5) | {category, confidence, neighbors, vote_counts} | ~1ms |
| 3c | Centroid Distance | 384-dim embedding + cached centroids | {category, confidence, distances} | ~2ms |
| 3d | Keyword Rules | description text | {category, confidence, scores} | ~1ms |

### Stage 4: AGGREGATE

| Step | Operation | Input | Output | Latency |
|------|-----------|-------|--------|---------|
| 4a | Phase Detection | 4 classifier votes + weight set | winning category + scenario (unanimous / supermajority / pair / 2v2 / disagreement) + scenario_cap | <1ms |
| 4b | Base Confidence | supporter avg conf, vote_share, weight_share | base = 0.60·supporter_avg + 0.25·vote_share + 0.15·weight_share | <1ms |
| 4c | Contextual Bonuses | error_codes, graph_confirms | +0.03 (errors), +0.02 (graph) | <1ms |
| 4d | Safety Check | max supporter conf, active count | base capped at 0.55 if max supporter conf < 0.60 and ≥3 active | <1ms |
| 4e | Caps | scenario_cap, quality_cap | final = min(base + bonus, scenario_cap, quality_cap) | <1ms |

### Stage 5: DECIDE + ENRICH

| Step | Operation | Input | Output | Latency |
|------|-----------|-------|--------|---------|
| 5a | Route/Escalate Decision | confidence vs 0.70 threshold | "routed" or "escalated" | <1ms |
| 5b | Team Lookup | category + priority | team name from routing_rules | ~5ms |
| 5c | Resolution Selection | 3 sources (similar, error, graph) | Best resolution_steps by effectiveness | ~1ms |
| 5d | Runbook Matching | category + resolution_steps | Runbook key + title | ~5ms |
| 5e | Expert Recommendation | graph_context.experts | Best expert name | <1ms |

**Total pipeline latency**: ~2,000ms (classifiers run in parallel via asyncio.gather — LLM-dominated). Without LLM (Level 2): ~100-300ms.

---

## 5. Classifier Algorithms — Detailed Logic

### 5.1 LLM Classifier (weight: 0.40, accuracy: 94.1%)

**Algorithm**: Context-injected root-cause classification via Qwen 2.5:7B (upgraded from 3B for better reasoning).

**Step-by-step**:

1. **Build context section** — Format all Stage 2 results into a structured prompt:
   - Infrastructure context (server type, datacenter, team, services, experts)
   - Similar past tickets (category, priority, title, resolution)
   - Error-matched past tickets

2. **Compose system prompt** — Root-cause classification instruction with 6 category definitions, 4 priority levels, and disambiguation rules (classify by root cause, not symptom).

3. **Call Ollama** — OpenAI-compatible chat completions endpoint:

```python
# From llm_classifier.py
async with httpx.AsyncClient(timeout=TIMEOUT) as client:
    resp = await client.post(
        f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
        json={
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        },
    )
```

4. **Parse response** — Extract JSON from LLM output, handling markdown code blocks:

```python
# From llm_classifier.py — _parse_llm_response()
text = text.strip()
if text.startswith("```"):
    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
if text.endswith("```"):
    text = text[:-3].strip()
# Try direct parse, then find JSON object in text
start = text.find("{")
end = text.rfind("}")
if start != -1 and end != -1:
    return json.loads(text[start:end + 1])
```

5. **Validate** — Category must be one of 6 valid values; priority one of 4; confidence clamped to [0.0, 1.0]:

```python
valid_cats = {"Infrastructure", "Application", "Database", "Network", "Security", "Access Management"}
valid_pris = {"critical", "high", "medium", "low"}
category = result.get("category")
if category not in valid_cats:
    category = None
confidence = max(0.0, min(1.0, float(confidence)))
```

**System prompt disambiguation rules** (from actual code):
```
- "502 errors because PostgreSQL is down" = Database (not Application)
- "VPN drops after firewall rule change" = Network (not Security)
- "SSO login failing after Active Directory update" = Access Management (not Infrastructure)
- "API slow because of missing database index" = Database (not Application)
```

**Failure modes**: Returns `{"category": None, "confidence": 0.0}` on `httpx.ConnectError` or any exception.

---

### 5.2 KNN Classifier (weight: 0.15, accuracy: 76.5%)

**Algorithm**: Similarity-weighted K-Nearest Neighbors voting on vector search results.

**Step-by-step**:

1. **Take top K** neighbors (K=5) from vector search results.

2. **Weighted vote** — Each neighbor votes for its category, weighted by cosine similarity score:

```python
# From knn_classifier.py
weighted_votes = {}
for ticket in top_k:
    cat = ticket.get("category")
    sim = ticket.get("similarity", 0.5)
    if cat:
        weighted_votes[cat] = weighted_votes.get(cat, 0) + sim
```

**Formula**:

```
score(category_c) = SUM( similarity_i )  for all neighbors i where category_i == c
winner = argmax_c( score(category_c) )
```

3. **Compute confidence** — Similarity-weighted vote share: the winner's summed similarity divided by the total summed similarity across all neighbors (unweighted vote counts are kept only for transparency):

```python
# From knn_classifier.py
winner_score = weighted_votes[winner]
total_score = sum(weighted_votes.values())
confidence = winner_score / total_score if total_score > 0 else 0.0
```

**Formula**:

```
confidence = SUM(similarity_i for neighbors agreeing with winner) / SUM(similarity_i for all neighbors)
```

**Example**: If top 5 are [Database(0.95), Database(0.91), Database(0.88), Application(0.82), Database(0.80)]:
- `weighted_votes = {"Database": 3.54, "Application": 0.82}`
- Winner = Database, confidence = 3.54 / 4.36 ≈ 0.812

---

### 5.3 Centroid Classifier (weight: 0.30, accuracy: 73.5%)

**Algorithm**: Cosine distance to pre-computed category centroid embeddings.

**Step-by-step**:

1. **Load centroids** — 6 pre-computed centroid embeddings (one per category), cached in-memory for 1 hour:

```python
# From centroid_classifier.py — _load_centroids()
for doc in db.collection("category_centroids").all():
    if doc.get("embedding"):
        centroids.append({
            "category": doc["category"],
            "embedding": doc["embedding"],
            "ticket_count": doc.get("ticket_count", 0),
        })
```

2. **Compute cosine similarity** to each centroid:

```python
# From centroid_classifier.py — _cosine_similarity()
a = np.array(a)
b = np.array(b)
dot = np.dot(a, b)
norm_a = np.linalg.norm(a)
norm_b = np.linalg.norm(b)
return float(dot / (norm_a * norm_b))
```

**Formula**:

```
cosine_similarity(a, b) = (a . b) / (||a|| * ||b||)
```

3. **Select winner** — Category with highest similarity.

4. **Compute gap-based confidence** — The gap between the top-1 and top-2 similarity scores determines confidence:

```python
# From centroid_classifier.py
sorted_sims = sorted(similarities.values(), reverse=True)
if len(sorted_sims) >= 2:
    gap = sorted_sims[0] - sorted_sims[1]
    confidence = min(0.5 + gap * 5, 0.99)
else:
    confidence = best_sim
```

**Formula**:

```
gap = sim_top1 - sim_top2
confidence = min(0.5 + gap * 5, 0.99)
```

**Example**: If similarities are `{Database: 0.92, Infrastructure: 0.78, Application: 0.65, ...}`:
- gap = 0.92 - 0.78 = 0.14
- confidence = min(0.5 + 0.14 * 5, 0.99) = min(1.20, 0.99) = 0.99

**Example** (close categories): `{Database: 0.85, Application: 0.82}`:
- gap = 0.03
- confidence = min(0.5 + 0.03 * 5, 0.99) = 0.65 (low confidence due to ambiguity)

---

### 5.4 Keyword Classifier (weight: 0.15, accuracy: 67.7%)

**Algorithm**: Dictionary-based keyword counting per category.

**Step-by-step**:

1. **Lowercase input text**.

2. **Count substring matches** across 6 category dictionaries (25+ keywords each):

```python
# From keyword_classifier.py
KEYWORD_DICT = {
    "Infrastructure": ["cpu", "memory", "ram", "disk", "server", "vm", "container",
                       "kubernetes", "docker", "restart", "crash", "oom", "kernel", ...],
    "Database":       ["postgres", "postgresql", "mysql", "oracle", "redis", "mongo",
                       "sql", "query", "index", "table", "schema", "migration", ...],
    "Network":        ["ssl", "vpn", "firewall", "dns", "tcp", "udp", "latency",
                       "packet", "route", "subnet", "bandwidth", "proxy", ...],
    "Security":       ["authentication", "authorization", "rbac", "token", "encryption",
                       "breach", "vulnerability", "malware", "phishing", ...],
    "Application":    ["api", "http", "endpoint", "bug", "error", "exception", "timeout",
                       "response", "frontend", "backend", "deploy", ...],
    "Access Management": ["ldap", "active directory", "sso", "saml", "oauth", "mfa",
                       "rbac", "permissions", "kerberos", "identity", "provisioning", ...],
}
```

3. **Compute scores** per category:

```python
# From keyword_classifier.py — uses word-boundary matching to avoid false positives
import re
for category, keywords in KEYWORD_DICT.items():
    score = 0
    for kw in keywords:
        if " " in kw:
            if kw in text_lower:  # Multi-word: substring match
                score += 1
        else:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):  # Single word: boundary match
                score += 1
    scores[category] = score
```

4. **Confidence** = winner's score / total matches:

```python
winner = max(scores, key=scores.get)
confidence = scores[winner] / max(total, 1)
```

**Formula**:

```
score(category_c) = count of keywords in KEYWORD_DICT[c] that appear in text
confidence = score(winner) / SUM(all scores)
```

**Example**: Text = "PostgreSQL connection pool exhausted, API returning 503 errors":
- Database: 2 (postgresql, connection pool)
- Application: 3 (api, error, 503)
- Winner = Application, confidence = 3/5 = 0.60

Note: Despite Application winning keyword count, the KNN and Centroid classifiers (which understand semantics) would likely vote Database, and the LLM would reason about root cause. This demonstrates why ensemble voting outperforms any single classifier.

---

## 6. Aggregation Algorithm — 6-Phase Majority-Aware Voting

### Constants

```python
# From aggregator.py (tuned via eval — ATR-55)
WEIGHTS = {
    "llm": 0.40,
    "knn": 0.15,       # reduced from 0.30 — similar tickets less reliable than centroid
    "centroid": 0.30,  # boosted from 0.20 — category center distance is very reliable
    "keyword": 0.15,   # boosted from 0.10 — useful fallback after word-boundary fix
}

DEGRADED_WEIGHTS = {
    "no_data":    {"llm": 0.80, "keyword": 0.20},
    "no_llm":     {"knn": 0.25, "centroid": 0.50, "keyword": 0.25},
    "emergency":  {"keyword": 1.0},
}

QUALITY_CAPS = {
    "HIGH":   0.99,
    "MEDIUM": 0.85,
    "LOW":    0.69,   # below the 0.70 auto-route line → vague tickets always escalate
}

SCENARIO_CAPS = {
    "unanimous_4":          0.95,
    "unanimous_3":          0.88,
    "unanimous_2":          0.75,
    "strong_supermajority": 0.85,
    "weak_supermajority":   0.65,
    "dissenter_override":   0.60,
    "pair_wins":            0.70,
    "pair_fallback":        0.60,
    "boundary_override":    0.65,
    "weighted_2v2":         0.65,
    "avgconf_2v2":          0.60,
    "centroid_tiebreak":    0.60,
    "unresolved_2v2":       0.50,
    "total_disagreement":   0.50,
    "single_classifier":    0.50,
}
```

### Step-by-Step Algorithm

**Step 0: Filter + Select Weights**

```python
# Filter classifiers that returned None category
active_votes = {k: v for k, v in votes.items() if v.get("category")}
weights = _get_weights(active_votes)
```

Weight selection logic:
- All 4 active: `{llm: 0.40, knn: 0.15, centroid: 0.30, keyword: 0.15}`
- No LLM: `{knn: 0.25, centroid: 0.50, keyword: 0.25}`
- LLM + Keywords only: `{llm: 0.80, keyword: 0.20}`
- Keywords only: `{keyword: 1.0}`
- Other combination: even split `1.0 / n` per active classifier

**Step 1: Tally votes and weighted scores**

```python
# vote_count = how many classifiers chose each category
# weighted_score = SUM(weight_i) per category, used only as a tiebreaker
category_voters = defaultdict(list)   # cat -> [{weight, confidence}, ...]
for classifier, vote in active_votes.items():
    cat = vote["category"]
    category_voters[cat].append({
        "weight": weights.get(classifier, 0),
        "confidence": vote.get("confidence", 0.5),
    })
total_active = len(active_votes)
```

Winner selection is deterministic: sort categories by `(vote_count desc, weighted_score desc, category_name asc)`.

**Step 2: Phase detection (which scenario applies)**

The winner and its `scenario_cap` are chosen by the first matching phase, not by a weighted sum:

| Phase | Scenario | Trigger | scenario_cap |
|-------|----------|---------|--------------|
| 0 | `single_classifier` | only 1 active classifier | 0.50 |
| 1 | unanimous | all active agree | `unanimous_4` 0.95 / `unanimous_3` 0.88 / `unanimous_2` 0.75 |
| 2 | supermajority | 3+ agree | `strong_supermajority` 0.85 / `weak_supermajority` 0.65 / `dissenter_override` 0.60 (by strength) |
| 3 | pair beats singles (2/1/1) | a 2-vote category vs two 1-vote categories | `pair_wins` 0.70 / `pair_fallback` 0.60 (strength-checked) |
| 4 | 2v2 split | known boundary (Database/Infrastructure) → `boundary_override` 0.65; else `weighted_2v2` 0.65 / `avgconf_2v2` 0.60 / `centroid_tiebreak` 0.60 / `unresolved_2v2` 0.50 | 0.50–0.65 |
| 5 | total disagreement | all categories tied at 1 vote | `total_disagreement` 0.50 (weighted fallback) |

**Step 3: Base confidence (computed over the winner's supporters)**

```python
voters = category_voters[winner]
supporter_avg_conf = sum(v["confidence"] for v in voters) / len(voters)
vote_share         = len(voters) / max(total_active, 1)
total_weight       = sum(v["weight"] for cv in category_voters.values() for v in cv)
weight_share       = sum(v["weight"] for v in voters) / max(total_weight, 0.01)

base = (0.60 * supporter_avg_conf) + (0.25 * vote_share) + (0.15 * weight_share)
```

**Step 4: Contextual bonuses**

```python
bonus = 0.0
if error_codes and errors_confirm_category(error_codes, winner):
    bonus += 0.03       # Error code confirms category
if graph_confirms_category:
    bonus += 0.02       # Graph context confirms category
```

**Step 5: Disagreement safety check**

Prevents dangerous high-confidence wrong routing. If no supporter of the winner is itself >60% confident (and ≥3 classifiers are active), the base is capped at 0.55 to trigger escalation:

```python
max_supporter_conf = max(v["confidence"] for v in voters)
if max_supporter_conf < 0.60 and total_active >= 3:
    base = min(base, 0.55)
```

**Step 6: Caps (scenario + quality)**

```python
quality_cap = QUALITY_CAPS.get(quality_score, 0.99)
final_confidence = round(min(base + bonus, scenario_cap, quality_cap), 3)
```

There is **no** agreement bonus (+0.05/-0.10) and **no** calibration multiplier (×0.98/×0.95/×0.80/×0.75); the scenario cap and quality cap are the only ceilings.

**Secondary Category**

```python
sorted_cats = sorted(category_scores.items(), key=lambda x: -x[1])
secondary = None
if len(sorted_cats) >= 2 and sorted_cats[1][1] > 0.15:
    secondary = sorted_cats[1][0]
```

### Complete Worked Example

**Scenario**: Ticket: "PostgreSQL connection pool exhausted on web-prod-01, API returning 503"

**Stage 1 output**:
- Entities: `servers=["web-prod-01"]`, `services=["postgresql-main"]`, `error_codes=[{error_key: "ERR-PG-003", pattern: "connection pool exhausted", service: "postgresql", severity: "high"}]`
- Quality: `"HIGH"` (description > 50 chars, has server + error code)

**Stage 3 classifier votes**:

| Classifier | Category | Confidence |
|-----------|----------|------------|
| LLM | Database | 0.92 |
| KNN | Database | 0.80 |
| Centroid | Database | 0.84 |
| Keyword | Application | 0.60 |

**Step 0**: All 4 active. Weights = `{llm: 0.40, knn: 0.15, centroid: 0.30, keyword: 0.15}`.

**Step 1**: Vote tally — `Database = 3 votes` (LLM, KNN, Centroid), `Application = 1 vote` (Keyword). Weighted (tiebreaker only) scores:
```
Database    = 0.40 + 0.15 + 0.30 = 0.85   (weight sum of its 3 supporters)
Application = 0.15                          (Keyword weight = 0.15 × ... , vote weight 0.15)
```
Winner = **Database** by `(vote_count=3 desc)`.

**Step 2**: Phase detection — 3 of 4 agree on Database (a 3/1 split) → **Phase 2 supermajority**. Supporter confidences are all ≥ 0.80, so this is a **strong supermajority** → `scenario_cap = 0.85`.

**Step 3**: Base confidence over the 3 Database supporters:
```
supporter_avg_conf = (0.92 + 0.80 + 0.84) / 3 = 0.853
vote_share         = 3 / 4 = 0.75
weight_share       = (0.40 + 0.15 + 0.30) / 1.00 = 0.85
base = 0.60·0.853 + 0.25·0.75 + 0.15·0.85
     = 0.512 + 0.1875 + 0.1275 = 0.827
```

**Step 4**: Contextual bonuses:
- `errors_confirm_category(["ERR-PG-003" service="postgresql"], "Database")` → `postgresql` maps to `Database` → **match**: `bonus += 0.03`
- Graph context: `managed_by_domain == "Database"` → **match**: `bonus += 0.02`
- Total bonus = 0.03 + 0.02 = **0.05** → `base + bonus = 0.827 + 0.05 = 0.877`

**Step 5**: Safety check — max supporter confidence is 0.92 (≥ 0.60), so no 0.55 cap applies.

**Step 6**: Caps:
- `scenario_cap = 0.85` (strong supermajority), `quality_cap = 0.99` (HIGH)
- `final_confidence = round(min(0.877, 0.85, 0.99), 3) = 0.85`

**Secondary category**:
- `Application` weighted score = 0.15. Is 0.15 > 0.15? No → **secondary = None**

**Final output**:
```json
{
    "category": "Database",
    "secondary_category": null,
    "priority": "high",
    "confidence": 0.85,
    "agreement": "3/4",
    "quality_score": "HIGH",
    "reasoning": "PostgreSQL connection pool exhaustion is a database-layer issue..."
}
```

**Decision**: 0.85 >= 0.70 → **Auto-routed** to Database Admin team.

---

## 7. Database Query Patterns

### 7.1 Vector Similarity Search

```sql
-- From retrieval.py — search_similar_tickets()  (PRIMARY path: ANN vector index)
-- Finds top 5 semantically similar past tickets using the ArangoDB vector index
-- via APPROX_NEAR_COSINE on 384-dimensional MiniLM embeddings.
-- APPROX_NEAR_COSINE cannot be combined with a pre-FILTER in the same loop, so we
-- over-fetch the nearest neighbours, then filter status and recompute EXACT cosine
-- on the survivors. Includes both "closed" (seed/synthetic) and "resolved"
-- (user-resolved) tickets — a live feedback loop where resolutions improve suggestions.

FOR ticket IN (
    FOR t IN tickets
        SORT APPROX_NEAR_COSINE(t.embedding, @embedding) DESC
        LIMIT @overfetch
        RETURN t
)
    FILTER ticket.status IN ["closed", "resolved"]
    LIMIT @limit
    LET sim = COSINE_SIMILARITY(ticket.embedding, @embedding)
    LET resolution = FIRST(
        FOR res IN 1..1 OUTBOUND ticket resolved_with
            RETURN res
    )
    RETURN {
        key: ticket._key,
        title: ticket.title,
        category: ticket.category,
        priority: ticket.priority,
        description: LEFT(ticket.description, 200),
        similarity: sim,
        resolution_steps: resolution.steps,
        effectiveness: resolution.effectiveness
    }
```

A brute-force exact full-scan (`FOR ticket IN tickets FILTER status IN ["closed","resolved"] LET sim = COSINE_SIMILARITY(...) SORT sim DESC LIMIT @limit`) is the **fallback only**, used when the vector index / `APPROX_NEAR_COSINE` is unavailable (e.g. index not yet built on a fresh deploy).

**Bind vars**: `{"embedding": [0.012, -0.034, ...], "limit": 5, "overfetch": 25}`

**Index used**: `idx_tickets_embedding` (vector, faiss-based IVF, 384-dim, cosine, nLists=10) — matches the Key Indexes table in 05.

### 7.2 Error Code → Ticket Traversal

```sql
-- From retrieval.py — search_by_error_codes()
-- Follows triggered_by edges from error_codes to tickets that had the same error.

FOR ticket IN 1..1 OUTBOUND CONCAT("error_codes/", @error_key) triggered_by
    FILTER ticket.status == "closed"
    LET resolution = FIRST(
        FOR res IN 1..1 OUTBOUND ticket resolved_with
            RETURN res
    )
    RETURN {
        key: ticket._key,
        title: ticket.title,
        category: ticket.category,
        error_code: @error_key,
        resolution_steps: resolution.steps,
        effectiveness: resolution.effectiveness
    }
```

**Bind vars**: `{"error_key": "ERR-PG-003"}`

**Edge traversal**: `error_codes/ERR-PG-003` -[triggered_by]-> `tickets/*`

### 7.3 Infrastructure Graph Traversal (Multi-hop)

```sql
-- From retrieval.py — traverse_graph()
-- Starting from a server, traverses hosts, managed_by, affects, and member_of
-- edges to build full infrastructure context in a single query.

LET server = DOCUMENT(CONCAT("servers/", @server_key))

LET services = (
    FOR svc IN 1..1 OUTBOUND server hosts
        RETURN svc.name
)

LET team = FIRST(
    FOR t IN 1..1 OUTBOUND server managed_by
        RETURN t
)

LET past_tickets = (
    FOR ticket IN 1..1 INBOUND server affects
        FILTER ticket.status == "closed"
        SORT ticket.created_at DESC
        LIMIT 5
        LET resolution = FIRST(
            FOR res IN 1..1 OUTBOUND ticket resolved_with
                RETURN res
        )
        RETURN {
            key: ticket._key,
            title: ticket.title,
            category: ticket.category,
            resolution_steps: resolution.steps,
            effectiveness: resolution.effectiveness
        }
)

LET experts = (
    FOR eng IN 1..1 INBOUND team member_of
        RETURN { name: eng.name, role: eng.role, expertise: eng.expertise }
)

RETURN {
    server_type: server.type,
    server_datacenter: server.datacenter,
    team_name: team.name,
    team_domain: team.domain,
    services: services,
    past_tickets: past_tickets,
    experts: experts
}
```

**Bind vars**: `{"server_key": "web-prod-01"}`

**Edge traversal path**:
```
server -[hosts]-> services
server -[managed_by]-> team
server <-[affects]- tickets -[resolved_with]-> resolutions
team <-[member_of]- engineers
```

### 7.4 Service Dependency Lookup

```sql
-- From retrieval.py — traverse_graph() (dependency section)
-- Finds services that depend on a given service.

FOR dep IN 1..1 INBOUND CONCAT("services/", @svc_key) depends_on
    RETURN dep.name
```

**Bind vars**: `{"svc_key": "postgresql-main"}`

### 7.5 Fulltext Keyword Search

```sql
-- From retrieval.py — search_fulltext()
-- Uses ArangoDB's built-in FULLTEXT() function on the description field.

FOR doc IN FULLTEXT(tickets, "description", @term)
    FILTER doc.status == "closed"
    LIMIT @limit
    RETURN {
        key: doc._key,
        title: doc.title,
        category: doc.category,
        description: LEFT(doc.description, 150)
    }
```

**Bind vars**: `{"term": "postgresql", "limit": 5}`

**Index used**: `idx_tickets_description_ft` (fulltext)

### 7.6 Routing Rule Lookup (Team Assignment)

```sql
-- From orchestrator.py — lookup_team()
-- Joins routing_rules with teams to find the target team for a category+priority.

FOR rule IN routing_rules
    FILTER rule.category == @category
    AND rule.priority == @priority
    AND rule.is_active == true
    FOR team IN teams
        FILTER team._key == rule.target_team
        RETURN team.name
```

**Bind vars**: `{"category": "Database", "priority": "high"}`

**Index used**: `idx_rules_category_priority` (persistent, composite)

### 7.7 Runbook Lookup

```sql
-- From orchestrator.py — find_runbook()
-- Finds runbooks matching the classified category.

FOR rb IN runbooks
    FILTER rb.category == @category
    RETURN { key: rb._key, title: rb.title }
```

**Bind vars**: `{"category": "Database"}`

### 7.8 Assigned-to Edge Management

```sql
-- From api/tickets.py — update_ticket_status()
-- Removes old assignment edge before creating a new one.

FOR e IN assigned_to
    FILTER e._from == CONCAT("tickets/", @ticket_id)
    REMOVE e IN assigned_to
```

**Bind vars**: `{"ticket_id": "12345"}`

---

## 8. Error Handling Strategy

### 8.1 By Layer

| Layer | Strategy | Implementation |
|-------|----------|----------------|
| **API Layer** (`api/tickets.py`) | HTTPException with appropriate status codes | `503` if DB unavailable, `404` if ticket not found, `400` for invalid status transitions |
| **Orchestrator** (`orchestrator.py`) | Graceful degradation via health check levels | Skips unavailable classifiers, always returns a result |
| **Retrieval** (`retrieval.py`) | Independent try/except per search method | Each of 4 searches fails independently, returns empty list on error |
| **Classifiers** (all 4) | Return `{category: None, confidence: 0.0}` on failure | Aggregator filters out None votes |
| **Database** (`database.py`) | Port check before connection, returns None on failure | Backend starts without DB (Level 1/3 degradation) |
| **Cache** (`cache.py`) | Returns None on connection failure | System works without Redis |

### 8.2 Classifier Failure Handling

```
Classifier fails → returns {category: None}
                        │
                        ▼
             Aggregator filters it out:
             active_votes = {k:v for k,v in votes.items() if v.get("category")}
                        │
                        ▼
             _get_weights() redistributes weights to remaining classifiers
                        │
                        ▼
             If ALL fail → returns {category: None, confidence: 0.0}
```

### 8.3 LLM-Specific Error Handling

```python
# From llm_classifier.py
try:
    # ... Ollama call ...
except httpx.ConnectError:
    logger.warning("Ollama not reachable at %s", settings.OLLAMA_BASE_URL)
    return {"category": None, "confidence": 0.0, "reasoning": "Ollama unavailable"}
except Exception as exc:
    logger.error("LLM classification failed: %s", exc)
    return {"category": None, "confidence": 0.0, "reasoning": f"Error: {exc}"}
```

### 8.4 Edge Creation Failures (Non-Blocking)

Edge creation (assigned_to, resolved_with, references, audit_log) is wrapped in try/except and logged as warnings. The main operation (ticket creation/update) still succeeds.

```python
# From api/tickets.py — create_ticket()
try:
    if result["recommended_team"]:
        team_key = _lookup_team_key(db, result["recommended_team"])
        if team_key:
            db.collection("assigned_to").insert({
                "_from": f"tickets/{ticket_key}",
                "_to": f"teams/{team_key}",
            })
except Exception as exc:
    logger.warning("Failed to create edges for ticket %s: %s", ticket_key, exc)
```

### 8.5 Degradation Level Matrix

| Level | Ollama | ArangoDB Data | Redis | Available Classifiers | Fallback |
|-------|--------|---------------|-------|----------------------|----------|
| 4 (Full) | UP | YES | UP/DOWN | LLM + KNN + Centroid + Keyword | None needed |
| 3 (No Data) | UP | NO | UP/DOWN | LLM + Keyword | LLM dominates (0.80) |
| 2 (No LLM) | DOWN | YES | UP/DOWN | KNN + Centroid + Keyword | Data-driven classifiers |
| 1 (Emergency) | DOWN | NO | UP/DOWN | Keyword only | Best-effort keyword match |

---

## 9. Caching Strategy — 3-Layer Hierarchy

### Layer 1: In-Process Singletons (Python Memory)

| Cache | Location | TTL | What is Cached | Size |
|-------|----------|-----|----------------|------|
| Embedding model | `orchestrator._embedding_model` | Infinite (process lifetime) | `SentenceTransformer("all-MiniLM-L6-v2")` model | ~80MB |
| Category centroids | `centroid_classifier._cached_centroids` | 3600s (1 hour) | 6 category embedding vectors (384-dim each) | ~18KB |
| Health status | `orchestrator._health_cache` | 5s | `HealthStatus` dict | ~100B |

**Implementation pattern** (centroid example):

```python
# From centroid_classifier.py
_cached_centroids: list[dict] | None = None
_cache_time: float = 0
CACHE_TTL = 3600  # 1 hour

def _load_centroids(db) -> list[dict]:
    global _cached_centroids, _cache_time
    now = time.time()
    if _cached_centroids and (now - _cache_time) < CACHE_TTL:
        return _cached_centroids
    # ... load from DB ...
    _cached_centroids = centroids
    _cache_time = now
    return centroids
```

### Layer 2: Entity Cache (In-Process, DB-Backed)

| Cache | Location | TTL | What is Cached | Size |
|-------|----------|-----|----------------|------|
| Server keys | `entity_extractor._server_keys` | 300s (5 min) | List of server _key strings | ~1KB |
| Service keys + names | `entity_extractor._service_keys`, `._service_names` | 300s (5 min) | Service _keys + name-to-key mapping | ~2KB |
| Error patterns | `entity_extractor._error_patterns` | 300s (5 min) | Error patterns with severity and service | ~5KB |

**Implementation pattern**:

```python
# From entity_extractor.py
CACHE_TTL = 300  # 5 minutes

def refresh_cache(self, db) -> None:
    now = time.time()
    if now - self._last_refresh < CACHE_TTL and self._server_keys:
        return  # cache still valid
    # ... load from DB ...
    self._last_refresh = now
```

### Layer 3: Redis (External, Shared)

| Cache | TTL | Purpose |
|-------|-----|---------|
| Health check | 5s | Avoid repeated Ollama/DB pings |
| Entity lists | 5 min | Avoid repeated DB scans (future: shared across workers) |

**Implementation**:

```python
# From cache.py
_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
await _redis.ping()
```

**Cache hierarchy flow**:
```
Request arrives
    │
    ├── Check in-process cache (Layer 1) → HIT: return immediately (~0ms)
    │
    ├── Check entity cache (Layer 2) → HIT if within 5-min TTL (~0ms)
    │
    ├── Check Redis (Layer 3) → HIT if another worker cached it (~1ms)
    │
    └── Load from ArangoDB → MISS: query DB, populate all cache layers (~5-20ms)
```

---

## 10. Schema & Index Design

### 10.1 Document Collections (13)

| Collection | Key Fields | Purpose |
|-----------|------------|---------|
| `tickets` | `_key`, title, description, category, secondary_category, priority, status, confidence_score, ai_reasoning, quality_score, classifier_votes, submitted_by, routed_to, embedding(384), suggested_resolution, resolution_effectiveness, suggested_runbook, recommended_expert, picked_up_by, created_at, resolved_at, `_source` | Primary ticket storage |
| `teams` | `_key`, name, domain | IT teams (6 teams) |
| `engineers` | `_key`, name, role, expertise | Team members (12) |
| `servers` | `_key`, type, datacenter | Infrastructure nodes (15) |
| `services` | `_key`, name | Software services (12) |
| `network_devices` | `_key`, type, location | Routers, switches, firewalls |
| `error_codes` | `_key`, pattern, service, severity | Known error patterns (20) |
| `runbooks` | `_key`, title, category, embedding(384) | Resolution playbooks (10) |
| `resolutions` | `_key`, steps, effectiveness, embedding(384) | Past resolution records (30 seed; grows as tickets are resolved) |
| `routing_rules` | `_key`, category, priority, target_team, is_active | Category+priority → team mapping (24) |
| `audit_log` | `_key`, ticket_id, action, actor, old_value, new_value, confidence_score, confidence_signals, reasoning, created_at | Full audit trail |
| `category_centroids` | `_key`, category, embedding(384), ticket_count | Pre-computed average embedding per category (6) |
| `users` | `_key`, email (unique), password_hash, role, first_name, last_name, engineer_key, team_key, is_active | Authentication accounts (RBAC) |

### 10.2 Edge Collections (9)

| Edge Collection | From | To | Meaning |
|----------------|------|-----|---------|
| `hosts` | servers | services | Server hosts a service |
| `managed_by` | servers, services | teams | Server/service is managed by team |
| `depends_on` | services | services | Service depends on another service |
| `member_of` | engineers | teams | Engineer belongs to team |
| `affects` | tickets | servers, services | Ticket affects server/service |
| `assigned_to` | tickets | teams | Ticket is assigned to team |
| `resolved_with` | tickets | resolutions | Ticket was resolved with these steps |
| `references` | resolutions | runbooks | Resolution used this runbook |
| `triggered_by` | error_codes | tickets | Error code appeared in this ticket |

### 10.3 Named Graph

```python
# From schema.py
GRAPH_NAME = "deskmind_graph"
GRAPH_EDGE_DEFINITIONS = [
    {"edge_collection": "hosts",
     "from_vertex_collections": ["servers"],
     "to_vertex_collections": ["services"]},
    {"edge_collection": "managed_by",
     "from_vertex_collections": ["servers", "services"],
     "to_vertex_collections": ["teams"]},
    {"edge_collection": "depends_on",
     "from_vertex_collections": ["services"],
     "to_vertex_collections": ["services"]},
    {"edge_collection": "member_of",
     "from_vertex_collections": ["engineers"],
     "to_vertex_collections": ["teams"]},
    {"edge_collection": "affects",
     "from_vertex_collections": ["tickets"],
     "to_vertex_collections": ["servers", "services"]},
    {"edge_collection": "assigned_to",
     "from_vertex_collections": ["tickets"],
     "to_vertex_collections": ["teams"]},
    {"edge_collection": "resolved_with",
     "from_vertex_collections": ["tickets"],
     "to_vertex_collections": ["resolutions"]},
    {"edge_collection": "references",
     "from_vertex_collections": ["resolutions"],
     "to_vertex_collections": ["runbooks"]},
    {"edge_collection": "triggered_by",
     "from_vertex_collections": ["error_codes"],
     "to_vertex_collections": ["tickets"]},
]
```

### 10.4 Index Catalog

| Index Name | Collection | Type | Fields | Parameters | Purpose |
|-----------|-----------|------|--------|------------|---------|
| `idx_tickets_category` | tickets | persistent | `[category]` | | Filter by category |
| `idx_tickets_priority` | tickets | persistent | `[priority]` | | Filter by priority |
| `idx_tickets_status` | tickets | persistent | `[status]` | | Filter by status (closed, routed, etc.) |
| `idx_tickets_created_at` | tickets | persistent | `[created_at]` | | Sort by date |
| `idx_tickets_title_ft` | tickets | fulltext | `[title]` | | FULLTEXT() search on titles |
| `idx_tickets_description_ft` | tickets | fulltext | `[description]` | | FULLTEXT() search on descriptions |
| `idx_tickets_embedding` | tickets | vector | `[embedding]` | dimension=384, metric=cosine, nLists=10 | COSINE_SIMILARITY vector search |
| `idx_runbooks_embedding` | runbooks | vector | `[embedding]` | dimension=384, metric=cosine, nLists=10 | Runbook similarity search |
| `idx_resolutions_embedding` | resolutions | vector | `[embedding]` | dimension=384, metric=cosine, nLists=10 | Resolution similarity search |
| `idx_rules_category_priority` | routing_rules | persistent | `[category, priority]` | | Composite lookup for routing |
| `idx_audit_ticket_id` | audit_log | persistent | `[ticket_id]` | | Filter audit entries by ticket |
| `idx_audit_created_at` | audit_log | persistent | `[created_at]` | | Sort audit entries by date |
| `idx_users_email` | users | persistent (unique) | `[email]` | unique=true | Fast login lookup, prevent duplicate accounts |

### 10.5 Vector Index Configuration

```python
# From schema.py — _create_indexes()
vector_params = {"dimension": 384, "metric": "cosine", "nLists": 10}

# Applied to: tickets, runbooks, resolutions
col.add_index({
    "type": "vector",
    "fields": ["embedding"],
    "params": vector_params,
    "name": idx_name,
})
```

- **Dimension**: 384 (matches `all-MiniLM-L6-v2` output)
- **Metric**: Cosine similarity (normalized dot product)
- **nLists**: 10 (IVF partitions for approximate nearest neighbor search)
- **Retry**: Up to 5 attempts with 5-second delay (vector subsystem needs initialization time after ArangoDB startup)

### 10.6 Graph Visualization

```
                    ┌──────────────┐
                    │  engineers   │
                    │  (12 docs)   │
                    └──────┬───────┘
                           │ member_of
                           ▼
  ┌────────────┐    ┌──────────────┐    ┌──────────────┐
  │  servers   │───▶│    teams     │◀───│  services    │
  │  (15 docs) │ m. │   (6 docs)  │ m. │  (12 docs)   │
  └──────┬─────┘ by └──────────────┘ by └──────┬───────┘
         │                                      │
         │ hosts                      depends_on │◀──┐
         ▼                                      ▼    │
  ┌──────────────┐                       ┌──────┘    │
  │  services    │                       │ services  │
  └──────────────┘                       └───────────┘

  ┌────────────┐  assigned_to  ┌──────────────┐
  │  tickets   │──────────────▶│    teams     │
  │ (855 docs) │               └──────────────┘
  │            │  affects       ┌──────────────┐
  │            │──────────────▶│servers/svc   │
  │            │               └──────────────┘
  │            │  resolved_with ┌──────────────┐  references  ┌──────────────┐
  │            │───────────────▶│ resolutions  │─────────────▶│   runbooks   │
  └──────┬─────┘               │  (30 docs)   │              │  (10 docs)   │
         ▲                     └──────────────┘              └──────────────┘
         │ triggered_by
  ┌──────┴─────┐
  │error_codes │
  │  (20 docs) │
  └────────────┘

  ┌────────────┐  engineer_key  ┌──────────────┐  team_key   ┌──────────────┐
  │   users    │───────────────▶│  engineers   │────────────▶│    teams     │
  │  (auth)    │                │ (knowledge)  │  member_of  │   (6 docs)   │
  └────────────┘                └──────────────┘             └──────────────┘
```

---

## 11. Resolution Pipeline — Decision Logic

### Resolution Source Priority

The orchestrator checks 3 sources in order, keeping the resolution with the highest effectiveness score:

```python
# From orchestrator.py — classify()
best_effectiveness = 0

# Source 1: Resolutions from similar tickets (same category)
if context["similar_tickets"]:
    for t in context["similar_tickets"]:
        if t.get("resolution_steps") and t["category"] == result["category"]:
            eff = t.get("effectiveness") or 0.8
            if eff > best_effectiveness:
                suggested_resolution = t["resolution_steps"]
                resolution_effectiveness = eff
                best_effectiveness = eff

# Source 2: Resolutions from error-matched tickets
if context["error_matched_tickets"]:
    for t in context["error_matched_tickets"]:
        if t.get("resolution_steps") and t["category"] == result["category"]:
            eff = t.get("effectiveness") or 0.8
            if eff > best_effectiveness:
                suggested_resolution = t["resolution_steps"]
                resolution_effectiveness = eff
                best_effectiveness = eff

# Source 3: Resolutions from graph context (past tickets on same server)
if graph_ctx and graph_ctx.get("past_tickets_on_server"):
    for t in graph_ctx["past_tickets_on_server"]:
        if t.get("resolution_steps") and t.get("category") == result["category"]:
            eff = t.get("effectiveness") or 0.8
            if eff > best_effectiveness:
                suggested_resolution = t["resolution_steps"]
                resolution_effectiveness = eff
                best_effectiveness = eff
```

### Effectiveness Learning

When an engineer resolves a ticket, the effectiveness score is computed based on whether they used the AI suggestion:

```python
# From api/tickets.py — resolve_ticket()
if resolve.used_ai_suggestion == "yes":
    effectiveness = 1.0       # AI suggestion confirmed working
elif resolve.used_ai_suggestion == "partially":
    effectiveness = 0.85      # Partially useful
else:
    effectiveness = 0.90      # New fix, assume good
```

This creates a feedback loop: future tickets matching the same error pattern or vector similarity will surface the highest-effectiveness resolution.

---

## 12. Audit Trail Design

Every classification and status change is logged to the `audit_log` collection:

### Classification Audit Entry

```python
# From api/tickets.py — create_ticket()
db.collection("audit_log").insert({
    "ticket_id": ticket_key,
    "action": "classified" if status == "routed" else "escalated",
    "actor": f"ai-{result['degradation_level']}-classifier-ensemble",
    "old_value": None,
    "new_value": {
        "category": result["category"],
        "priority": result["priority"],
        "team": result["recommended_team"],
    },
    "confidence_score": result["confidence"],
    "confidence_signals": {
        "llm": result["classifier_votes"].get("llm", {}).get("confidence"),
        "knn": result["classifier_votes"].get("knn", {}).get("confidence"),
        "centroid": result["classifier_votes"].get("centroid", {}).get("confidence"),
        "keyword": result["classifier_votes"].get("keyword", {}).get("confidence"),
    },
    "reasoning": result["reasoning"],
    "created_at": now,
})
```

### Status Change Audit Entry

```python
# From api/tickets.py — update_ticket_status()
db.collection("audit_log").insert({
    "ticket_id": ticket_id,
    "action": update.status,
    "actor": user["email"],
    "old_value": {"status": old_status, "team": doc.get("routed_to")},
    "new_value": {"status": update.status, "team": new_team or doc.get("routed_to")},
    "confidence_score": None,
    "reasoning": f"Status changed by {user['email']}",
    "created_at": now,
})
```

### Resolution Audit Entry

```python
# From api/tickets.py — resolve_ticket()
db.collection("audit_log").insert({
    "ticket_id": ticket_id,
    "action": "resolved",
    "actor": user["email"],
    "old_value": {"status": doc.get("status")},
    "new_value": {
        "status": "resolved",
        "resolution_steps": resolve.resolution_steps,
        "used_ai_suggestion": resolve.used_ai_suggestion,
        "used_runbook": resolve.used_runbook,
    },
    "confidence_score": None,
    "reasoning": f"Resolved by {user['email']}. AI suggestion {'used' if resolve.used_ai_suggestion == 'yes' else 'not used'}.",
    "created_at": now,
})
```

### Feedback Audit Entry

```python
# From api/tickets.py — submit_feedback()
db.collection("audit_log").insert({
    "ticket_id": ticket_id,
    "action": "feedback",
    "actor": user["email"],
    "old_value": None,
    "new_value": {
        "rating": feedback.rating,
        "comment": feedback.comment,
    },
    "confidence_score": doc.get("confidence_score"),
    "reasoning": f"AI suggestion rated '{feedback.rating}' by {user['email']}",
    "created_at": now,
})
```

**Actor format**: AI actions are tagged as `ai-{level}-classifier-ensemble` (e.g., `ai-4-classifier-ensemble`), distinguishing them from human actions by email address.

---

## 13. Error-to-Category Confirmation Map

The `errors_confirm_category()` function provides a static mapping used for the +0.03 confidence bonus in the aggregator:

```python
# From error_scanner.py
service_to_category = {
    "postgresql": "Database",
    "redis": "Database",
    "nginx": "Application",
    "order-service": "Application",
    "auth-service": "Access Management",
    "kubernetes": "Infrastructure",
    "linux": "Infrastructure",
    "firewall": "Network",
    "vpn": "Network",
    "dns": "Network",
    "active-directory": "Access Management",
    "api-gateway": "Security",
    "nfs": "Infrastructure",
}
```

This mapping acts as a domain-knowledge shortcut: if a known error code associated with `postgresql` is detected and the ensemble votes `Database`, the confirmation bonus increases confidence by +0.03.

---

## 14. Ticket Lifecycle State Machine

```
                    POST /api/tickets
                          │
                          ▼
                 ┌────────────────┐
                 │   CLASSIFIED   │
                 └────────┬───────┘
                          │
              ┌───────────┴───────────┐
              │                       │
     confidence >= 0.70      confidence < 0.70
              │                       │
              ▼                       ▼
     ┌────────────────┐     ┌────────────────┐
     │    ROUTED      │     │   ESCALATED    │
     └────────┬───────┘     └────────┬───────┘
              │                       │
              │   PATCH /status       │
              ▼                       ▼
     ┌────────────────┐     ┌────────────────┐
     │  IN_PROGRESS   │◀───▶│   REASSIGNED   │
     └────────┬───────┘     └────────────────┘
              │
              │   POST /resolve
              ▼
     ┌────────────────┐
     │   RESOLVED     │
     └────────────────┘

Status transitions enforced by API:
  - Cannot update resolved/closed tickets
  - Valid PATCH statuses: {in_progress, escalated, routed}
```

---

## 15. Post-R2 Improvements (Finals)

### 15.1 AI Resolution Generator (`resolution_generator.py`)

**Purpose**: When no good historical resolution exists (effectiveness < 0.50), the LLM generates a custom step-by-step fix grounded in real data.

```python
async def generate_resolution(
    title, description, category, priority,
    entities, similar_tickets, graph_context, error_codes,
) -> dict | None:
    """Returns {steps: [...], reasoning: str, confidence: str, sources_used: [...]}"""
```

**Quality gate**: Only generates when at least 1 reference resolution OR graph context OR error codes exist. Returns `None` otherwise (no hallucination).

**LLM prompt**: System prompt instructs "Base your steps ONLY on the reference solutions provided. Do NOT invent server names or commands." Temperature: 0.2 (slightly creative but grounded).

**Integration point**: Orchestrator Stage 5, after historical resolution lookup:
```python
if (not suggested_resolution or effectiveness < 0.5) and confidence >= 0.60:
    generated = await generate_resolution(...)
```

### 15.2 Text Preprocessing (`orchestrator.preprocess_text()`)

Cleans ticket text before embedding to reduce noise:
```python
def preprocess_text(title, description) -> str:
    text = f"{title}. {description}"
    # Remove timestamps (ISO, syslog)
    # Replace IP addresses with IP_ADDR token
    # Remove UUIDs
    # Remove long file paths
    # Collapse whitespace, truncate to 2000 chars
```

Applied both at classification time and during seed data loading (consistent embedding space).

### 15.3 Title + Description Co-Embedding

**Before (R2)**: Only description was embedded: `model.encode(description)`
**After**: Title and description are co-encoded: `model.encode(preprocess_text(title, description))`

This was the single biggest accuracy improvement: **+8.8%** (85.3% → 94.1%). Titles like "RBAC policy preventing access" immediately suggest Access Management, but if only the description ("kubectl commands return Forbidden...") is embedded, the vector lands near Infrastructure.

### 15.4 KNN Weighted Confidence

**Before**: `confidence = agreeing_neighbors / k` (count-based)
**After**: `confidence = winner_weighted_score / total_weighted_score` (proportional to similarity strength)

When 3 neighbors vote Database with 0.95 similarity and 2 vote Application with 0.30, the old formula says 60%. The new formula says 83%.

### 15.5 Retrieval Re-ranking

After vector search returns top 5 similar tickets, results are re-ranked by combined score:
```
rank_score = 0.60 × similarity + 0.20 × recency + 0.20 × effectiveness
```
Recent, proven resolutions surface above old/unverified ones.

### 15.6 Cache Invalidation on Corrections

When an engineer overrides a ticket category:
1. Correction recorded in `corrections` collection (tracks which classifiers were wrong/right)
2. Centroids optionally recomputed from corrected tickets
3. **Both cache tiers flushed** — Tier A (exact match deleted), Tier B (all entries cleared)

### 15.7 Multi-Signal Quality Scorer

**Before**: Simple 50-char threshold
**After**: 5-signal scorer:
- Infrastructure entities (servers/services): +3
- Error codes: +3
- Description length (>40/+1, >100/+2)
- Technical keywords: +1
- Title specificity (>15 chars): +1

Score >= 5 = HIGH, >= 3 = MEDIUM, < 3 = LOW. "PostgreSQL down on prod-db-01" correctly scores HIGH (was LOW before).

### 15.8 Evaluation Benchmark (`scripts/evaluate.py`)

Fixed 35-ticket test set with hand-labeled ground truth covering:
- 5 tickets per category (clear + boundary cases)
- 5 edge cases (very short, multi-domain, vague)
- Supports `--tag` for naming runs and `--compare` for side-by-side comparison

Metrics: overall accuracy, per-category accuracy/confidence, per-difficulty accuracy, individual classifier accuracy, confusion matrix, misclassification details.

### 15.9 Majority-Aware Voting Algorithm

Replaced simple weighted voting with 6-phase algorithm:
- Phase 0: Single classifier (cap 0.50)
- Phase 1: Unanimous (cap 0.95)
- Phase 2: Supermajority 3+ with strength check
- Phase 3: Pair beats singles 2/1/1
- Phase 4: 2v2 split with known boundary overrides (e.g., Database vs Infrastructure)
- Phase 5: Total disagreement → weighted fallback (cap 0.50)

Confidence formula: `0.60 × supporter_avg_conf + 0.25 × vote_share + 0.15 × weight_share`

### 15.10 Incident Prediction (`api/incidents.py`)

Proactive detection of 3 pattern types:
- **Cluster**: 3+ tickets routed to same team in 4 hours
- **Trend**: Category volume 50%+ higher than last week
- **Spike**: 5+ new tickets in 1 hour

Role-based filtering: Admin sees all, Engineer sees own team + spikes, User sees spikes only. Cached 60s per role+team.

### 15.11 OCR Screenshot Analysis (`services/ocr_engine.py`)

Processes uploaded screenshots with Tesseract OCR:
- Preprocesses images (grayscale, contrast 1.5x, sharpen, resize)
- Classifies screenshot type: stack_trace, http_error, log_output, terminal, monitoring_dashboard, general
- Extracts text → runs entity extraction → feeds to all 4 classifiers
- Max 5 attachments per ticket, 5MB each
