"""ArangoDB schema initialization — collections, edges, graph, indexes."""

import logging

from arango.database import StandardDatabase

logger = logging.getLogger(__name__)

# ── Document collections ──
DOCUMENT_COLLECTIONS = [
    "tickets",
    "teams",
    "engineers",
    "servers",
    "services",
    "network_devices",
    "error_codes",
    "runbooks",
    "resolutions",
    "routing_rules",
    "audit_log",
    "category_centroids",
    "users",
    "corrections",
    "repeated_issues",
]

# ── Edge collections ──
EDGE_COLLECTIONS = [
    "hosts",
    "managed_by",
    "depends_on",
    "member_of",
    "affects",
    "assigned_to",
    "resolved_with",
    "references",
    "triggered_by",
]

# ── Named graph definition ──
GRAPH_NAME = "deskmind_graph"
GRAPH_EDGE_DEFINITIONS = [
    {"edge_collection": "hosts", "from_vertex_collections": ["servers"], "to_vertex_collections": ["services"]},
    {"edge_collection": "managed_by", "from_vertex_collections": ["servers", "services"], "to_vertex_collections": ["teams"]},
    {"edge_collection": "depends_on", "from_vertex_collections": ["services"], "to_vertex_collections": ["services"]},
    {"edge_collection": "member_of", "from_vertex_collections": ["engineers"], "to_vertex_collections": ["teams"]},
    {"edge_collection": "affects", "from_vertex_collections": ["tickets"], "to_vertex_collections": ["servers", "services"]},
    {"edge_collection": "assigned_to", "from_vertex_collections": ["tickets"], "to_vertex_collections": ["teams"]},
    {"edge_collection": "resolved_with", "from_vertex_collections": ["tickets"], "to_vertex_collections": ["resolutions"]},
    {"edge_collection": "references", "from_vertex_collections": ["resolutions"], "to_vertex_collections": ["runbooks"]},
    {"edge_collection": "triggered_by", "from_vertex_collections": ["error_codes"], "to_vertex_collections": ["tickets"]},
]


def init_schema(db: StandardDatabase) -> None:
    """Create all collections, edges, graph, and indexes. Idempotent."""

    # ── Document collections ──
    for name in DOCUMENT_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name)
            logger.info("Created document collection: %s", name)

    # ── Edge collections ──
    for name in EDGE_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name, edge=True)
            logger.info("Created edge collection: %s", name)

    # ── Named graph ──
    if not db.has_graph(GRAPH_NAME):
        db.create_graph(
            GRAPH_NAME,
            edge_definitions=GRAPH_EDGE_DEFINITIONS,
        )
        logger.info("Created graph: %s", GRAPH_NAME)

    # ── Indexes ──
    _create_indexes(db)

    logger.info("Schema initialization complete (%d document + %d edge collections, 1 graph)",
                len(DOCUMENT_COLLECTIONS), len(EDGE_COLLECTIONS))


def _create_indexes(db: StandardDatabase) -> None:
    """Create all indexes. Skips if already exist."""

    tickets = db.collection("tickets")
    routing_rules = db.collection("routing_rules")
    runbooks = db.collection("runbooks")
    resolutions = db.collection("resolutions")
    audit_log = db.collection("audit_log")

    # ── Persistent indexes on tickets ──
    tickets.add_persistent_index(fields=["category"], name="idx_tickets_category")
    tickets.add_persistent_index(fields=["priority"], name="idx_tickets_priority")
    tickets.add_persistent_index(fields=["status"], name="idx_tickets_status")
    tickets.add_persistent_index(fields=["created_at"], name="idx_tickets_created_at")
    logger.info("Created persistent indexes on tickets")

    # ── Full-text index on tickets ──
    # python-arango 8.x removed the add_fulltext_index() helper; create the same
    # fulltext index via the generic add_index() API. minLength=0 preserves the
    # old add_fulltext_index() default (index words of any length).
    # Unlike add_fulltext_index(), the generic add_index() is NOT idempotent — it
    # raises [ERR 1005] on a duplicate name — so skip indexes that already exist
    # (init_schema runs on every startup).
    existing_ticket_indexes = {i["name"] for i in tickets.indexes() if "name" in i}
    for field in ("title", "description"):
        idx_name = f"idx_tickets_{field}_ft"
        if idx_name not in existing_ticket_indexes:
            tickets.add_index({"type": "fulltext", "fields": [field], "minLength": 0, "name": idx_name})
    logger.info("Created full-text indexes on tickets")

    # ── Persistent index on routing_rules ──
    routing_rules.add_persistent_index(fields=["category", "priority"], name="idx_rules_category_priority")
    logger.info("Created persistent index on routing_rules")

    # ── Persistent indexes on audit_log ──
    audit_log.add_persistent_index(fields=["ticket_id"], name="idx_audit_ticket_id")
    audit_log.add_persistent_index(fields=["created_at"], name="idx_audit_created_at")
    logger.info("Created persistent indexes on audit_log")

    # ── Unique index on users.email ──
    users = db.collection("users")
    users.add_persistent_index(fields=["email"], name="idx_users_email", unique=True)
    logger.info("Created unique index on users.email")

    # ── Persistent indexes on corrections ──
    corrections = db.collection("corrections")
    corrections.add_persistent_index(fields=["ticket_id"], name="idx_corrections_ticket_id")
    corrections.add_persistent_index(fields=["is_trusted"], name="idx_corrections_trusted")
    corrections.add_persistent_index(fields=["created_at"], name="idx_corrections_created_at")
    logger.info("Created persistent indexes on corrections")

    # ── Vector indexes (384-dim, cosine similarity) ──
    # Vector subsystem may take time to initialize after ArangoDB starts.
    # Retry a few times with delay.
    import time
    vector_collections = [
        (tickets, "idx_tickets_embedding"),
        (runbooks, "idx_runbooks_embedding"),
        (resolutions, "idx_resolutions_embedding"),
    ]
    vector_params = {"dimension": 384, "metric": "cosine", "nLists": 10}

    for attempt in range(5):
        try:
            for col, idx_name in vector_collections:
                # Skip if already exists
                existing = [i["name"] for i in col.indexes() if "name" in i]
                if idx_name in existing:
                    continue
                col.add_index({
                    "type": "vector",
                    "fields": ["embedding"],
                    "params": vector_params,
                    "name": idx_name,
                })
            logger.info("Created vector indexes on tickets, runbooks, resolutions")
            break
        except Exception as exc:
            if attempt < 4:
                logger.info("Vector index not ready, retrying in 5s... (attempt %d/5)", attempt + 1)
                time.sleep(5)
            else:
                logger.warning("Vector indexes not created after 5 attempts: %s", exc)
