# DeskMind — Sequence Diagrams

> **Nasscom AI-Code-Sarathi Excel Hackathon — Final Round (Jury)**
> **Team**: Arif Asadullah, Aakarsh, Mohit Tomar
> **Date**: June 2026

---

## 1. Ticket Submission and Classification (Full Pipeline)

This diagram shows the complete end-to-end flow when a user submits a ticket
through the React frontend. It covers all 5 stages of the classification pipeline,
including parallel retrieval searches, parallel classifier execution, aggregation,
and the final routing decision.

```mermaid
sequenceDiagram
    autonumber
    participant User as IT Staff / User
    participant React as React Frontend
    participant API as FastAPI<br/>tickets.py
    participant Orch as Orchestrator<br/>orchestrator.py
    participant Health as check_health()
    participant Redis as Redis 7
    participant EE as EntityExtractor<br/>entity_extractor.py
    participant QS as QualityScorer<br/>quality_scorer.py
    participant MM as MiniLM Model<br/>all-MiniLM-L6-v2
    participant Ret as Retrieval<br/>retrieval.py
    participant ArangoDB as ArangoDB 3.12
    participant LLM as LLM Classifier<br/>llm_classifier.py
    participant Ollama as Ollama<br/>Qwen 2.5:7B
    participant KNN as KNN Classifier<br/>knn_classifier.py
    participant Cent as Centroid Classifier<br/>centroid_classifier.py
    participant KW as Keyword Classifier<br/>keyword_classifier.py
    participant Agg as Aggregator<br/>aggregator.py

    User ->> React: Submit ticket form<br/>(title, description, priority)
    React ->> API: POST /api/tickets<br/>Authorization: Bearer {token}<br/>TicketCreate {title, description, priority}

    Note over API: Auth: require_any_authenticated
    API ->> API: get_current_user() → user {email, role, team_key}
    API ->> API: Validate request via Pydantic<br/>submitted_by = user.email (from token)

    Note over API, Orch: Stage 0 -- Invoke Classification Pipeline
    API ->> Orch: classify(title, description, db, redis_client)
    activate Orch

    Note over Orch, Redis: Health Check (cached 5s TTL)
    Orch ->> Health: check_health(db, redis_client)
    activate Health
    Health ->> Redis: ping()
    Redis -->> Health: pong (redis_ok=true)
    Health ->> Ollama: GET /api/version
    Ollama -->> Health: 200 OK (ollama_ok=true)
    Health ->> ArangoDB: db.collection("tickets").count()
    ArangoDB -->> Health: 855 (db_has_data=true)
    Health -->> Orch: HealthStatus {ollama: true, db_has_data: true, redis: true, level: 4}
    deactivate Health

    Note over Orch, MM: Stage 1 -- Preparation
    Orch ->> EE: entity_extractor.extract(description, db)
    activate EE
    EE ->> EE: refresh_cache(db)<br/>Check CACHE_TTL (300s)
    EE ->> ArangoDB: collection("servers").all()<br/>collection("services").all()<br/>collection("error_codes").all()
    ArangoDB -->> EE: 15 server keys, 12 service keys,<br/>20 error patterns
    EE ->> EE: Match servers in text_lower<br/>Match services by key/name<br/>Match error patterns
    EE -->> Orch: ExtractedEntities {servers: ["db-primary-01"],<br/>services: ["postgresql"], error_codes: [{error_key: "ERR-DB-003", ...}]}
    deactivate EE

    Orch ->> QS: score_quality(title, description, entities)
    activate QS
    QS ->> QS: desc_len=183 > 50, has_entities=true,<br/>has_errors=true
    QS -->> Orch: "HIGH"
    deactivate QS

    Orch ->> MM: get_embedding_model().encode(description)
    activate MM
    MM -->> Orch: embedding: float[384]
    deactivate MM

    Note over Orch, ArangoDB: Stage 2 -- Retrieval (4 searches)
    Orch ->> Ret: retrieve_all(db, embedding, entities, description)
    activate Ret

    par Vector Similarity Search
        Ret ->> ArangoDB: search_similar_tickets(db, embedding, limit=5)<br/>AQL (primary): subquery SORT APPROX_NEAR_COSINE DESC LIMIT overfetch,<br/>then FILTER status IN ['closed','resolved'], recompute exact COSINE_SIMILARITY<br/>(brute-force COSINE_SIMILARITY full-scan is fallback only)<br/>+ resolved_with traversal
        ArangoDB -->> Ret: similar_tickets: list[SimilarTicket] (5 results)
    and Error Code Match
        Ret ->> ArangoDB: search_by_error_codes(db, error_codes)<br/>AQL: 1..1 OUTBOUND error_codes triggered_by<br/>+ resolved_with traversal
        ArangoDB -->> Ret: error_matched_tickets: list[dict]
    and Graph Traversal
        Ret ->> ArangoDB: traverse_graph(db, entities)<br/>AQL: server -> hosts -> services<br/>server -> managed_by -> teams<br/>teams <- member_of <- engineers<br/>server <- affects <- tickets
        ArangoDB -->> Ret: GraphContext {managed_by_team: "Database Admin",<br/>managed_by_domain: "Database",<br/>experts: [{name: "Priya Sharma", ...}], ...}
    and Full-text Search
        Ret ->> ArangoDB: search_fulltext(db, description, limit=5)<br/>AQL: FULLTEXT(tickets, "description", @term)<br/>per keyword (up to 5 terms)
        ArangoDB -->> Ret: fulltext_matches: list[dict]
    end

    Ret -->> Orch: RetrievalResult {similar_tickets,<br/>error_matched_tickets, graph_context, fulltext_matches}
    deactivate Ret

    Note over Orch, KW: Stage 3 -- Classification (4 classifiers in parallel via asyncio.gather)
    par LLM Classifier (weight: 0.40)
        Orch ->> LLM: classify_llm(title, description, context)
        activate LLM
        LLM ->> LLM: _build_context_section(context)<br/>Build SYSTEM_PROMPT + user_prompt
        LLM ->> Ollama: POST /v1/chat/completions<br/>{model: "qwen2.5:7b",<br/>messages: [system, user],<br/>temperature: 0.1}
        Ollama -->> LLM: {choices: [{message: {content: "JSON..."}}]}
        LLM ->> LLM: _parse_llm_response(content)<br/>Validate category in 6 valid_cats<br/>Validate priority in valid_pris<br/>Clamp confidence to [0.0, 1.0]
        LLM -->> Orch: {category: "Database", priority: "critical",<br/>confidence: 0.96, reasoning: "Root cause is..."}
        deactivate LLM
    and KNN Classifier (weight: 0.15)
        Orch ->> KNN: classify_knn(context.similar_tickets, k=5)
        activate KNN
        KNN ->> KNN: Take top K tickets<br/>Weighted vote by similarity<br/>confidence = agreeing / total
        KNN -->> Orch: {category: "Database", confidence: 0.80,<br/>vote_counts: {Database: 4, Application: 1}}
        deactivate KNN
    and Centroid Classifier (weight: 0.30)
        Orch ->> Cent: classify_centroid(embedding, db)
        activate Cent
        Cent ->> Cent: _load_centroids(db) (1h cache)
        Cent ->> ArangoDB: collection("category_centroids").all()
        ArangoDB -->> Cent: 6 centroid embeddings
        Cent ->> Cent: _cosine_similarity() vs 6 centroids<br/>confidence = 0.5 + gap * 5
        Cent -->> Orch: {category: "Database", confidence: 0.87,<br/>distances: {Database: 0.92, ...}}
        deactivate Cent
    and Keyword Classifier (weight: 0.15)
        Orch ->> KW: classify_keyword(description)
        activate KW
        KW ->> KW: Match KEYWORD_DICT<br/>(25+ keywords x 6 categories)<br/>confidence = winner / total
        KW -->> Orch: {category: "Database", confidence: 0.60,<br/>scores: {Database: 3, Application: 2, ...}}
        deactivate KW
    end

    Note over Orch, Agg: Stage 4 -- Aggregation
    Orch ->> Orch: graph_confirms = (graph_context.managed_by_domain == llm_category)
    Orch ->> Agg: aggregate(votes, quality_score="HIGH",<br/>error_codes=[{error_key: "ERR-DB-003", ...}],<br/>graph_confirms_category=true)
    activate Agg
    Agg ->> Agg: _get_weights(active_votes)<br/>{llm: 0.40, knn: 0.15, centroid: 0.30, keyword: 0.15}
    Agg ->> Agg: Phase select (6-phase majority-aware voting):<br/>all 4 classifiers vote Database -> Phase 1 unanimous<br/>scenario = unanimous_4 (SCENARIO_CAP = 0.95)
    Agg ->> Agg: Winner: sort by (vote_count desc, weighted_score desc, name asc)<br/>Database = 4 votes -> winner
    Agg ->> Agg: Confidence base = 0.60*supporter_avg + 0.25*vote_share + 0.15*weight_share<br/>supporter_avg = (0.96+0.80+0.87+0.60)/4 = 0.8075<br/>vote_share = 4/4 = 1.0, weight_share = 1.0<br/>base = 0.60*0.8075 + 0.25*1.0 + 0.15*1.0 = 0.8845
    Agg ->> Agg: Contextual bonus: errors_confirm_category() -> +0.03<br/>graph_confirms -> +0.02<br/>base + bonus = 0.8845 + 0.05 = 0.9345
    Agg ->> Agg: Safety: max_supporter_conf=0.96 >= 0.60 -> no 0.55 cap
    Agg ->> Agg: final = round(min(0.9345, SCENARIO_CAP 0.95, QUALITY_CAP HIGH 0.99), 3) = 0.934
    Agg -->> Orch: {category: "Database", secondary_category: null,<br/>priority: "critical", confidence: 0.934,<br/>agreement: "4/4", quality_score: "HIGH"}
    deactivate Agg

    Note over Orch, ArangoDB: Stage 5 -- Decision & Enrichment
    Orch ->> ArangoDB: lookup_team(db, "Database", "critical")<br/>AQL: routing_rules FILTER category+priority<br/>JOIN teams
    ArangoDB -->> Orch: "Database Admin"
    Orch ->> Orch: Select best resolution from 3 sources<br/>Source 1: similar_tickets (same category)<br/>Source 2: error_matched_tickets (highest effectiveness)<br/>Source 3: graph past_tickets_on_server
    Orch ->> ArangoDB: find_runbook(db, "Database", resolution_steps)<br/>AQL: runbooks FILTER category
    ArangoDB -->> Orch: "KB-0003: PostgreSQL Emergency Recovery"
    Orch ->> Orch: recommended_expert = graph_context.experts[0].name<br/>= "Priya Sharma"

    Orch -->> API: ClassificationResult {category: "Database",<br/>confidence: 0.934, recommended_team: "Database Admin",<br/>suggested_resolution: [...], recommended_expert: "Priya Sharma",<br/>processing_time_ms: 2147, ...17 fields total}
    deactivate Orch

    Note over API, ArangoDB: Post-Pipeline -- Persist & Respond

    alt confidence >= 0.70 (Auto-route)
        API ->> API: status = "routed"
    else confidence < 0.70 (Escalate)
        API ->> API: status = "escalated"
    end

    API ->> ArangoDB: collection("tickets").insert({<br/>title, description, category: "Database",<br/>priority: "critical", status: "routed",<br/>confidence_score: 0.934, embedding: float[384],<br/>routed_to: "Database Admin",<br/>suggested_resolution: ["Increase max_connections..."],<br/>resolution_effectiveness: 0.95,<br/>suggested_runbook: "KB-0003: PostgreSQL Emergency Recovery",<br/>recommended_expert: "Priya Sharma",<br/>_source: "user", ...})
    ArangoDB -->> API: {_key: "T-856"}
    Note right of ArangoDB: AI enrichment fields (suggested_resolution,<br/>resolution_effectiveness, suggested_runbook,<br/>recommended_expert) are stored directly<br/>in the ticket document — not just<br/>returned in the API response.

    API ->> API: _lookup_team_key(db, "Database Admin")
    API ->> ArangoDB: collection("assigned_to").insert({<br/>_from: "tickets/T-856", _to: "teams/db-admin"})

    API ->> ArangoDB: collection("audit_log").insert({<br/>ticket_id: "T-856", action: "classified",<br/>actor: "ai-4-classifier-ensemble",<br/>new_value: {category: "Database", priority: "critical",<br/>team: "Database Admin"},<br/>confidence_score: 0.934,<br/>confidence_signals: {llm: 0.96, knn: 0.80,<br/>centroid: 0.87, keyword: 0.60}})

    API -->> React: 201 Created<br/>TicketResponse {id: "T-856", category: "Database",<br/>status: "routed", confidence_score: 0.934,<br/>routed_to: "Database Admin",<br/>suggested_resolution: ["Increase max_connections..."],<br/>recommended_expert: "Priya Sharma", ...}
    React -->> User: Display routed ticket with<br/>AI reasoning, confidence, team,<br/>suggested resolution, expert
```

---

## 2. Engineer Status Update (PATCH Flow)

This diagram covers the PATCH `/api/tickets/{id}/status` endpoint, which allows
engineers to pick up tickets, reassign them to different teams, or escalate them.
It includes validation, edge management, and audit logging.

```mermaid
sequenceDiagram
    autonumber
    participant Eng as Engineer
    participant React as React Frontend
    participant API as FastAPI<br/>tickets.py
    participant ArangoDB as ArangoDB 3.12

    Eng ->> React: Click "Pick Up" / "Reassign" / "Escalate"
    React ->> API: PATCH /api/tickets/T-856/status<br/>Authorization: Bearer {token}<br/>TicketStatusUpdate {<br/>  status: "in_progress",<br/>  assigned_to: null<br/>}

    Note over API: Auth: require_engineer_or_admin
    API ->> API: get_current_user() → user {email, role, team_key}

    Note over API: Validation Phase
    API ->> ArangoDB: db.collection("tickets").get("T-856")
    ArangoDB -->> API: doc {status: "routed", routed_to: "Database Admin", ...}

    API ->> API: require_team_access(doc.routed_to, user, db)<br/>Engineer must belong to ticket's team

    alt Ticket not found
        API -->> React: 404 "Ticket not found"
        React -->> Eng: Error: Ticket not found
    else Wrong team (engineer)
        API -->> React: 403 "You can only access tickets assigned to your team"
        React -->> Eng: Error: Not your team's ticket
    else Status not in {in_progress, escalated, routed}
        API -->> React: 400 "Invalid status. Must be one of: {in_progress, escalated, routed}"
        React -->> Eng: Error: Invalid status
    else doc.status in ("resolved", "closed")
        API -->> React: 400 "Cannot update status of resolved/closed ticket"
        React -->> Eng: Error: Cannot update resolved ticket
    else status == "in_progress" AND doc.picked_up_by != user.email
        API -->> React: 409 "Ticket already picked up by {doc.picked_up_by}"
        React -->> Eng: Error: Ticket already picked up by another engineer
    else Valid status update
        Note over API: Build Update Fields
        API ->> API: old_status = doc.status  # "routed"<br/>update_fields = {_key: "T-856", status: "in_progress"}

        opt assigned_to is provided (Reassignment)
            Note over API, ArangoDB: Edge Management -- Reassign to new team
            API ->> API: new_team = update.assigned_to<br/>update_fields["routed_to"] = new_team
            API ->> API: _lookup_team_key(db, new_team)
            API ->> ArangoDB: collection("teams").all()<br/>FILTER name == new_team
            ArangoDB -->> API: team_key (e.g., "infra-ops")

            alt team_key found
                API ->> ArangoDB: AQL: FOR e IN assigned_to<br/>  FILTER e._from == "tickets/T-856"<br/>  REMOVE e IN assigned_to
                ArangoDB -->> API: Old edge removed
                API ->> ArangoDB: collection("assigned_to").insert({<br/>  _from: "tickets/T-856",<br/>  _to: "teams/infra-ops"<br/>})
                ArangoDB -->> API: New edge created
            else team_key not found
                API ->> API: Log warning, skip edge update
            end
        end

        Note over API: Set picked_up_by (ownership tracking)
        API ->> API: if status == "in_progress":<br/>  update_fields["picked_up_by"] = user.email<br/>elif status in ("escalated", "routed"):<br/>  update_fields["picked_up_by"] = null

        Note over API, ArangoDB: Apply Update
        API ->> ArangoDB: collection("tickets").update({<br/>  _key: "T-856",<br/>  status: "in_progress",<br/>  picked_up_by: "priya@company.com"<br/>})
        ArangoDB -->> API: Updated

        Note over API, ArangoDB: Audit Log
        API ->> ArangoDB: collection("audit_log").insert({<br/>  ticket_id: "T-856",<br/>  action: "in_progress",<br/>  actor: "priya@company.com",<br/>  old_value: {status: "routed", team: "Database Admin"},<br/>  new_value: {status: "in_progress", team: "Database Admin"},<br/>  confidence_score: null,<br/>  reasoning: "Status changed by priya@company.com",<br/>  created_at: "2026-04-28T14:35:00Z"<br/>})

        Note over API: Fetch Updated Document
        API ->> ArangoDB: collection("tickets").get("T-856")
        ArangoDB -->> API: Updated doc {status: "in_progress", ...}
        API ->> API: _doc_to_response(updated_doc)

        API -->> React: 200 OK<br/>TicketResponse {<br/>  id: "T-856",<br/>  status: "in_progress",<br/>  routed_to: "Database Admin",<br/>  ...all fields<br/>}
        React -->> Eng: Display updated ticket<br/>Status badge: "In Progress"
    end
```

---

## 3. Ticket Resolution (POST Flow)

This diagram covers the POST `/api/tickets/{id}/resolve` endpoint. It shows
how resolution data is persisted, embeddings are generated for future similarity
search, effectiveness scores are calculated, and knowledge graph edges are created
to link the ticket to its resolution and any referenced runbook.

```mermaid
sequenceDiagram
    autonumber
    participant Eng as Engineer
    participant React as React Frontend
    participant API as FastAPI<br/>tickets.py
    participant ST as SentenceTransformer<br/>all-MiniLM-L6-v2
    participant ArangoDB as ArangoDB 3.12

    Eng ->> React: Fill resolution form<br/>(steps, AI suggestion feedback, runbook)
    React ->> API: POST /api/tickets/T-856/resolve<br/>Authorization: Bearer {token}<br/>TicketResolve {<br/>  resolution_steps: [<br/>    "Increased max_connections from 100 to 200",<br/>    "Restarted PostgreSQL service",<br/>    "Verified order-service reconnected"<br/>  ],<br/>  used_ai_suggestion: "yes",<br/>  used_runbook: "KB-0003"<br/>}

    Note over API: Auth: require_engineer_or_admin
    API ->> API: get_current_user() → user {email: "priya@company.com", role: "engineer"}
    API ->> API: require_team_access(doc.routed_to, user, db)

    Note over API: Validation Phase
    API ->> ArangoDB: collection("tickets").get("T-856")
    ArangoDB -->> API: doc {status: "in_progress", category: "Database",<br/>suggested_resolution: ["Increase max_connections..."], ...}

    alt Ticket not found
        API -->> React: 404 "Ticket not found"
    else doc.status == "closed"
        API -->> React: 400 "Ticket is already closed"
    else Valid resolution
        Note over API, ST: Generate Resolution Embedding
        API ->> ST: SentenceTransformer("all-MiniLM-L6-v2")<br/>model.encode("Increased max_connections from 100 to 200<br/>Restarted PostgreSQL service<br/>Verified order-service reconnected")
        ST -->> API: embedding: float[384]

        Note over API: Calculate Effectiveness Score
        alt used_ai_suggestion == "yes"
            API ->> API: effectiveness = 1.0<br/>(confirmed AI suggestion works)
        else used_ai_suggestion == "partially"
            API ->> API: effectiveness = 0.85<br/>(partially useful)
        else used_ai_suggestion == "no"
            API ->> API: effectiveness = 0.90<br/>(new fix, assume good)
        end

        Note over API, ArangoDB: Create Resolution Document
        API ->> ArangoDB: collection("resolutions").insert({<br/>  steps: ["Increased max_connections...",<br/>    "Restarted PostgreSQL service",<br/>    "Verified order-service reconnected"],<br/>  effectiveness: 1.0,<br/>  embedding: float[384]<br/>})
        ArangoDB -->> API: {_key: "R-831"}

        Note over API, ArangoDB: Create resolved_with Edge<br/>(ticket -> resolution)
        API ->> ArangoDB: collection("resolved_with").insert({<br/>  _from: "tickets/T-856",<br/>  _to: "resolutions/R-831"<br/>})
        ArangoDB -->> API: Edge created

        opt used_runbook is provided
            Note over API, ArangoDB: Create references Edge<br/>(resolution -> runbook)
            API ->> ArangoDB: collection("references").insert({<br/>  _from: "resolutions/R-831",<br/>  _to: "runbooks/KB-0003"<br/>})
            ArangoDB -->> API: Edge created
        end

        Note over API, ArangoDB: Update Ticket Status
        API ->> ArangoDB: collection("tickets").update({<br/>  _key: "T-856",<br/>  status: "resolved",<br/>  resolved_at: "2026-04-28T15:20:00Z"<br/>})
        ArangoDB -->> API: Updated

        Note over API, ArangoDB: Audit Log
        API ->> ArangoDB: collection("audit_log").insert({<br/>  ticket_id: "T-856",<br/>  action: "resolved",<br/>  actor: "priya@company.com",<br/>  old_value: {status: "in_progress"},<br/>  new_value: {<br/>    status: "resolved",<br/>    resolution_steps: ["Increased max_connections...", ...],<br/>    used_ai_suggestion: "yes",<br/>    used_runbook: "KB-0003"<br/>  },<br/>  reasoning: "Resolved by priya@company.com. AI suggestion used.",<br/>  created_at: "2026-04-28T15:20:00Z"<br/>})

        Note over API: Fetch Final State
        API ->> ArangoDB: collection("tickets").get("T-856")
        ArangoDB -->> API: Final doc {status: "resolved", resolved_at: "...", ...}
        API ->> API: _doc_to_response(final_doc)

        API -->> React: 200 OK<br/>TicketResponse {<br/>  id: "T-856",<br/>  status: "resolved",<br/>  resolved_at: "2026-04-28T15:20:00Z",<br/>  ...all fields<br/>}
        React -->> Eng: Display resolved ticket<br/>Status badge: "Resolved"

        Note right of ArangoDB: Knowledge Graph Updated:<br/>tickets/T-856 --resolved_with--> resolutions/R-831<br/>resolutions/R-831 --references--> runbooks/KB-0003<br/><br/>Future tickets with similar embeddings<br/>will find this resolution via<br/>search_similar_tickets() and<br/>search_by_error_codes()
    end
```

---

## 4. Graceful Degradation Scenarios

DeskMind never goes fully offline. When components fail, the system automatically
detects the degradation level and adjusts classifier weights. This diagram shows
two failure scenarios: Level 2 (Ollama down, DB up) and Level 1 (Emergency mode).

### Scenario A -- Level 2: Ollama Down, Database Available

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI<br/>tickets.py
    participant Orch as Orchestrator<br/>orchestrator.py
    participant Health as check_health()
    participant Redis as Redis 7
    participant Ollama as Ollama<br/>(DOWN)
    participant EE as EntityExtractor
    participant QS as QualityScorer
    participant MM as MiniLM Model
    participant Ret as Retrieval
    participant ArangoDB as ArangoDB 3.12
    participant KNN as KNN Classifier
    participant Cent as Centroid Classifier
    participant KW as Keyword Classifier
    participant Agg as Aggregator

    API ->> Orch: classify(title, description, db, redis_client)
    activate Orch

    Note over Orch, Ollama: Health Check detects Ollama failure
    Orch ->> Health: check_health(db, redis_client)
    activate Health
    Health ->> Redis: ping()
    Redis -->> Health: pong
    Health ->> Ollama: GET /api/version (timeout=2.0s)
    Ollama --x Health: Connection refused / timeout
    Health ->> Health: ollama_ok = false
    Health ->> ArangoDB: db.collection("tickets").count()
    ArangoDB -->> Health: 855
    Health ->> Health: db_has_data = true
    Health ->> Health: level = 2 (No LLM:<br/>not ollama_ok and db_has_data)
    Health -->> Orch: HealthStatus {ollama: false, db_has_data: true,<br/>redis: true, level: 2}
    deactivate Health

    Note over Orch, MM: Stage 1 -- Preparation (unchanged)
    Orch ->> EE: entity_extractor.extract(description, db)
    EE -->> Orch: ExtractedEntities {servers, services, error_codes}
    Orch ->> QS: score_quality(title, description, entities)
    QS -->> Orch: "HIGH"
    Orch ->> MM: get_embedding_model().encode(description)
    MM -->> Orch: embedding: float[384]

    Note over Orch, ArangoDB: Stage 2 -- Retrieval (unchanged, DB is available)
    Orch ->> Ret: retrieve_all(db, embedding, entities, description)
    Ret ->> ArangoDB: search_similar_tickets() + search_by_error_codes()<br/>+ traverse_graph() + search_fulltext()
    ArangoDB -->> Ret: Full retrieval results
    Ret -->> Orch: RetrievalResult {similar_tickets, error_matched_tickets,<br/>graph_context, fulltext_matches}

    Note over Orch, KW: Stage 3 -- Classification (LLM SKIPPED)
    Orch ->> Orch: health.ollama == false<br/>logger.warning("Skipping LLM classifier (Ollama down)")

    par KNN Classifier (re-weighted: 0.25)
        Orch ->> KNN: classify_knn(context.similar_tickets, k=5)
        KNN -->> Orch: {category: "Database", confidence: 0.80,<br/>vote_counts: {Database: 4, Application: 1}}
    and Centroid Classifier (re-weighted: 0.50)
        Orch ->> Cent: classify_centroid(embedding, db)
        Cent ->> ArangoDB: _load_centroids(db)
        ArangoDB -->> Cent: 6 centroids
        Cent -->> Orch: {category: "Database", confidence: 0.87,<br/>distances: {Database: 0.92, ...}}
    and Keyword Classifier (re-weighted: 0.25)
        Orch ->> KW: classify_keyword(description)
        KW -->> Orch: {category: "Database", confidence: 0.60,<br/>scores: {Database: 3, ...}}
    end

    Note over Orch, Agg: Stage 4 -- Aggregation (degraded weights)
    Orch ->> Agg: aggregate(votes={knn, centroid, keyword},<br/>quality_score="HIGH", error_codes=[...],<br/>graph_confirms_category=true)
    activate Agg
    Agg ->> Agg: _get_weights(active_votes)<br/>llm not in active_keys<br/>Return DEGRADED_WEIGHTS["no_llm"]<br/>{knn: 0.25, centroid: 0.50, keyword: 0.25}
    Agg ->> Agg: Winner sort (votes desc, weighted desc, name asc):<br/>Database weighted = 0.25*0.80 + 0.50*0.87 + 0.25*0.60 = 0.785
    Agg ->> Agg: Phase 1 -- unanimous (3/3 Database)<br/>scenario = unanimous_3, SCENARIO_CAP = 0.88
    Agg ->> Agg: base = 0.60*supporter_avg + 0.25*vote_share + 0.15*weight_share<br/>supporter_avg=(0.80+0.87+0.60)/3=0.757, vote_share=1.0, weight_share=1.0<br/>base = 0.854
    Agg ->> Agg: Contextual bonus: error confirm +0.03, graph confirm +0.02<br/>base + bonus = 0.854 + 0.05 = 0.904
    Agg ->> Agg: final = round(min(0.904, SCENARIO_CAP 0.88, HIGH cap 0.99), 3) = 0.88
    Agg -->> Orch: {category: "Database", confidence: 0.88,<br/>agreement: "3/3"}
    deactivate Agg

    Note over Orch: Stage 5 -- Decision
    Orch ->> Orch: confidence 0.88 >= 0.70 -> status = "routed"<br/>Still routed successfully without LLM!

    Orch -->> API: ClassificationResult {category: "Database",<br/>confidence: 0.88, degradation_level: 2,<br/>processing_time_ms: ~250, ...}
    deactivate Orch

    Note right of API: Level 2 Result:<br/>Correct category: Database<br/>Confidence: 0.88 (vs 0.934 at Level 4)<br/>Latency: ~250ms (vs ~2100ms at Level 4)<br/>LLM reasoning: not available<br/>Priority: "medium" (LLM not available for priority)
```

### Scenario B -- Level 1: Emergency Mode (Ollama Down, Database Empty)

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI<br/>tickets.py
    participant Orch as Orchestrator<br/>orchestrator.py
    participant Health as check_health()
    participant Ollama as Ollama<br/>(DOWN)
    participant ArangoDB as ArangoDB 3.12<br/>(EMPTY)
    participant EE as EntityExtractor
    participant QS as QualityScorer
    participant MM as MiniLM Model
    participant KW as Keyword Classifier
    participant Agg as Aggregator

    API ->> Orch: classify(title, description, db, redis_client)
    activate Orch

    Note over Orch, ArangoDB: Health Check -- worst case
    Orch ->> Health: check_health(db, redis_client)
    activate Health
    Health ->> Ollama: GET /api/version (timeout=2.0s)
    Ollama --x Health: Connection refused
    Health ->> Health: ollama_ok = false
    Health ->> ArangoDB: db.collection("tickets").count()
    ArangoDB -->> Health: 0
    Health ->> Health: db_has_data = false
    Health ->> Health: level = 1 (Emergency:<br/>not ollama_ok and not db_has_data)
    Health -->> Orch: HealthStatus {ollama: false, db_has_data: false,<br/>redis: false, level: 1}
    deactivate Health

    Note over Orch, EE: Stage 1 -- Preparation (partial)
    Orch ->> Orch: db exists but db_has_data = false
    Orch ->> EE: entity_extractor.extract(description, db)
    EE ->> EE: refresh_cache(db)<br/>Collections exist but empty
    EE -->> Orch: ExtractedEntities {servers: [], services: [], error_codes: []}

    Orch ->> QS: score_quality(title, description, entities)
    QS ->> QS: desc_len > 50 but has_entities=false, has_errors=false
    QS -->> Orch: "MEDIUM" (cap = 0.85)

    Orch ->> MM: get_embedding_model().encode(description)
    MM -->> Orch: embedding: float[384] (computed but unused)

    Note over Orch: Stage 2 -- Retrieval SKIPPED
    Orch ->> Orch: health.db_has_data == false<br/>context = {similar_tickets: [],<br/>error_matched_tickets: [],<br/>graph_context: null, fulltext_matches: []}

    Note over Orch: Stage 3 -- Only Keyword Classifier available
    Orch ->> Orch: health.ollama == false -> Skip LLM
    Orch ->> Orch: health.db_has_data == false -> Skip KNN
    Orch ->> Orch: health.db_has_data == false -> Skip Centroid

    Orch ->> KW: classify_keyword(description)
    activate KW
    KW ->> KW: Match KEYWORD_DICT<br/>"postgresql" -> Database +1<br/>"connection" -> Database +1<br/>"503" -> Application +1<br/>Database: 2, Application: 1
    KW -->> Orch: {category: "Database", confidence: 0.667,<br/>scores: {Database: 2, Application: 1, ...}}
    deactivate KW

    Note over Orch, Agg: Stage 4 -- Aggregation (emergency weights)
    Orch ->> Agg: aggregate(votes={keyword: {...}},<br/>quality_score="MEDIUM",<br/>error_codes=[], graph_confirms_category=false)
    activate Agg
    Agg ->> Agg: _get_weights(active_votes)<br/>active_keys == {"keyword"}<br/>Return DEGRADED_WEIGHTS["emergency"]<br/>{keyword: 1.0}
    Agg ->> Agg: Phase 0 -- single classifier (only keyword active)<br/>scenario = single_classifier, SCENARIO_CAP = 0.50
    Agg ->> Agg: base = 0.60*supporter_avg + 0.25*vote_share + 0.15*weight_share<br/>= 0.60*0.667 + 0.25*1.0 + 0.15*1.0 = 0.800
    Agg ->> Agg: No error confirmation, no graph confirmation -> bonus = 0<br/>(single classifier, so no &lt;0.60 supporter safety cap either)
    Agg ->> Agg: final = round(min(0.800, SCENARIO_CAP 0.50, MEDIUM cap 0.85), 3) = 0.50
    Agg -->> Orch: {category: "Database", confidence: 0.50,<br/>agreement: "1/1"}
    deactivate Agg

    Note over Orch: Stage 5 -- Decision
    Orch ->> Orch: confidence 0.50 < 0.70 -> status = "escalated"<br/>System correctly escalates to human review

    Orch -->> API: ClassificationResult {category: "Database",<br/>confidence: 0.50, degradation_level: 1,<br/>recommended_team: null (no routing_rules in empty DB),<br/>processing_time_ms: ~120, ...}
    deactivate Orch

    API ->> API: status = "escalated"
    API ->> ArangoDB: collection("tickets").insert({<br/>status: "escalated", confidence_score: 0.50, ...})

    API -->> React: 201 Created<br/>TicketResponse {status: "escalated",<br/>confidence_score: 0.50,<br/>ai_reasoning: "",<br/>routed_to: null}
    React -->> Eng: Display escalated ticket<br/>Banner: "Low confidence -- needs human review"

    Note right of API: Level 1 Emergency Result:<br/>Category suggestion: Database (likely correct)<br/>Confidence: 0.50 (below 0.70 threshold)<br/>Status: ESCALATED to human<br/>Latency: ~120ms (fastest possible)<br/>No resolution, no expert, no runbook<br/>No LLM reasoning<br/><br/>The system never fully crashes --<br/>it always provides a best-effort<br/>classification with appropriate<br/>confidence signaling.
```

### Degradation Summary

| Aspect | Level 4 (Full) | Level 3 (No Data) | Level 2 (No LLM) | Level 1 (Emergency) |
|--------|---------------|-------------------|-------------------|---------------------|
| Classifiers | LLM + KNN + Centroid + Keyword | LLM + Keyword | KNN + Centroid + Keyword | Keyword only |
| Weights | 0.40, 0.15, 0.30, 0.15 | 0.80, 0.20 | 0.25, 0.50, 0.25 | 1.00 |
| Retrieval | All 4 searches | None (no data) | All 4 searches | None (no data) |
| Expected accuracy | ~90%+ | ~80% | ~70% | ~55% |
| Typical latency | 2-5s (parallel) | 2-5s (LLM dominates) | 150-300ms | 50-120ms |
| Resolution suggestion | Yes (3 sources) | No (no past tickets) | Yes (3 sources) | No (no past tickets) |
| Expert recommendation | Yes (from graph) | No (no graph data) | Yes (from graph) | No (no graph data) |
| Auto-route likely? | Yes (high confidence) | Yes (LLM is strong) | Yes (if data-backed) | No (escalates to human) |
| Priority source | LLM inference | LLM inference | Default "medium" | Default "medium" |

---

## 5. Authentication Flow (Login, Register, Token Refresh)

This diagram covers the JWT authentication flow — login, admin registration, and automatic token refresh.

```mermaid
sequenceDiagram
    autonumber
    participant User as User / Admin
    participant React as React Frontend
    participant API as FastAPI<br/>auth.py
    participant Auth as core/auth.py
    participant ArangoDB as ArangoDB 3.12

    Note over User, ArangoDB: Login Flow
    User ->> React: Enter email + password
    React ->> API: POST /api/auth/login<br/>UserLogin {email, password}
    API ->> ArangoDB: AQL: FOR u IN users<br/>FILTER u.email == @email LIMIT 1
    ArangoDB -->> API: user doc {email, password_hash, role, team_key, is_active}

    alt User not found OR password wrong
        API ->> Auth: verify_password(plain, hash)
        Auth -->> API: false
        API -->> React: 401 "Invalid email or password"
        React -->> User: Error: Invalid credentials
    else User deactivated
        API -->> React: 403 "Account is deactivated"
    else Valid credentials
        API ->> Auth: verify_password(plain, hash)
        Auth -->> API: true
        API ->> Auth: create_access_token({sub: email, role, team_key})
        Auth -->> API: JWT access token (30 min expiry)
        API ->> Auth: create_refresh_token({sub: email, role, team_key})
        Auth -->> API: JWT refresh token (7 day expiry)
        API -->> React: TokenResponse {access_token, refresh_token, token_type: "bearer"}
        React ->> React: localStorage.setItem("access_token", token)<br/>localStorage.setItem("refresh_token", token)
        React ->> API: GET /api/auth/me<br/>Authorization: Bearer {access_token}
        API ->> Auth: get_current_user(credentials)
        Auth ->> Auth: decode_token(token) → {sub, role, team_key}
        Auth ->> ArangoDB: Verify user active in DB
        ArangoDB -->> Auth: user doc
        Auth -->> API: user dict
        API -->> React: UserResponse {email, role, team_key, team_name}
        React -->> User: Redirect to Dashboard
    end

    Note over User, ArangoDB: Admin Registers New User
    User ->> React: Fill create user form<br/>(email, password, role, engineer_key)
    React ->> API: POST /api/auth/register<br/>Authorization: Bearer {admin_token}<br/>UserRegister {email, password, role: "engineer", engineer_key: "eng-001"}

    API ->> Auth: get_current_user() → admin user
    API ->> Auth: require_admin() → verify role == "admin"

    API ->> ArangoDB: collection("engineers").get("eng-001")
    ArangoDB -->> API: engineer doc {name: "Arjun Nair", ...}
    API ->> ArangoDB: AQL: member_of traversal → resolve team
    ArangoDB -->> API: team {_key: "db-admin", name: "Database Admin"}
    API ->> Auth: hash_password("changeme")
    Auth -->> API: "$2b$12$..."
    API ->> ArangoDB: collection("users").insert({<br/>email, password_hash, role: "engineer",<br/>engineer_key: "eng-001", team_key: "db-admin"})
    ArangoDB -->> API: created
    API -->> React: UserResponse {email, role: "engineer",<br/>team_key: "db-admin", team_name: "Database Admin"}
    React -->> User: User created successfully

    Note over React, Auth: Automatic Token Refresh (transparent to user)
    React ->> API: GET /api/tickets<br/>Authorization: Bearer {expired_token}
    API -->> React: 401 Unauthorized
    React ->> API: POST /api/auth/refresh<br/>{refresh_token: "eyJhb..."}
    API ->> Auth: decode_token(refresh_token)
    Auth -->> API: {sub, role, team_key, type: "refresh"}
    API ->> ArangoDB: Verify user still active
    ArangoDB -->> API: user doc (is_active: true)
    API ->> Auth: create_access_token({sub, role, team_key})
    Auth -->> API: new JWT access token
    API -->> React: TokenResponse {new access_token, new refresh_token}
    React ->> React: Update localStorage tokens
    React ->> API: GET /api/tickets (retry)<br/>Authorization: Bearer {new_token}
    API -->> React: 200 OK — tickets list
```

### Authentication Guard on Every Protected Endpoint

Every ticket/chat endpoint goes through this auth check before executing:

```
Request with Bearer token
    │
    ├── get_current_user()
    │       ├── decode_token() → extract {sub, role, team_key}
    │       ├── Query users collection → verify user exists + is_active
    │       └── Return user dict OR raise 401
    │
    ├── require_role() [if endpoint needs specific role]
    │       └── Check user.role in allowed_roles OR raise 403
    │
    └── require_team_access() [inline, for ticket mutations]
            ├── Admin → bypass
            ├── User → 403 "cannot modify"
            └── Engineer → resolve team_key → compare with ticket.routed_to OR raise 403
```

---

## Diagram Notation Reference

| Element | Meaning |
|---------|---------|
| Solid arrow (`->>`) | Synchronous call |
| Dashed arrow (`-->>`) | Return / response |
| Cross arrow (`--x`) | Failed call (connection error / timeout) |
| `par ... and ... end` | Parallel execution block |
| `alt ... else ... end` | Conditional branch |
| `opt ... end` | Optional block (executes only if condition met) |
| `activate` / `deactivate` | Lifespan of an active process |
| `Note over` | Annotation spanning participants |
| `Note right of` | Side annotation on a single participant |
