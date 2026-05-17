"""Knowledge graph API — returns nodes and edges for visualization."""

import logging

from fastapi import APIRouter, Depends, Request, Query

from backend.core.auth import require_any_authenticated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Collections to include as nodes
NODE_COLLECTIONS = ["teams", "engineers", "servers", "services", "network_devices", "error_codes"]

# Edge collections to include
EDGE_COLLECTIONS = [
    "hosts", "managed_by", "depends_on", "member_of",
    "affects", "assigned_to", "resolved_with", "triggered_by",
]

# Node type display config
NODE_CONFIG = {
    "teams": {"type": "team", "label_field": "name", "group": 1},
    "engineers": {"type": "engineer", "label_field": "name", "group": 2},
    "servers": {"type": "server", "label_field": "_key", "group": 3},
    "services": {"type": "service", "label_field": "_key", "group": 4},
    "network_devices": {"type": "network_device", "label_field": "_key", "group": 5},
    "error_codes": {"type": "error_code", "label_field": "_key", "group": 6},
    "tickets": {"type": "ticket", "label_field": "title", "group": 7},
}


@router.get("")
async def get_graph(
    request: Request,
    user: dict = Depends(require_any_authenticated),
    category: str | None = Query(None, description="Filter by category"),
):
    """Return full knowledge graph as nodes + edges for visualization."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        return {"nodes": [], "edges": []}

    nodes = []
    edges = []
    node_ids = set()

    try:
        # ── Load infrastructure nodes ──
        for col_name in NODE_COLLECTIONS:
            config = NODE_CONFIG[col_name]
            try:
                cursor = db.aql.execute(f"FOR doc IN {col_name} LIMIT 500 RETURN doc")
                for doc in cursor:
                    node_id = f"{col_name}/{doc['_key']}"
                    label = doc.get(config["label_field"], doc["_key"])
                    node = {
                        "id": node_id,
                        "label": label if len(str(label)) < 40 else str(label)[:37] + "...",
                        "type": config["type"],
                        "group": config["group"],
                        "data": _extract_node_data(col_name, doc),
                    }
                    nodes.append(node)
                    node_ids.add(node_id)
            except Exception as exc:
                logger.warning("Failed to load %s: %s", col_name, exc)

        # ── Load user tickets as nodes ──
        ticket_filter = "t._source != null"
        if category:
            ticket_filter += f' AND t.category == "{category}"'

        try:
            cursor = db.aql.execute(
                f"FOR t IN tickets FILTER {ticket_filter} SORT t.created_at DESC LIMIT 200 RETURN t"
            )
            config = NODE_CONFIG["tickets"]
            for doc in cursor:
                node_id = f"tickets/{doc['_key']}"
                label = f"#{doc['_key']}: {doc.get('title', '')}"
                if len(label) > 40:
                    label = label[:37] + "..."
                nodes.append({
                    "id": node_id,
                    "label": label,
                    "type": config["type"],
                    "group": config["group"],
                    "data": {
                        "id": doc.get("_key"),
                        "title": doc.get("title"),
                        "category": doc.get("category"),
                        "priority": doc.get("priority"),
                        "status": doc.get("status"),
                        "confidence": doc.get("confidence_score"),
                        "routed_to": doc.get("routed_to"),
                        "created_at": doc.get("created_at"),
                    },
                })
                node_ids.add(node_id)
        except Exception as exc:
            logger.warning("Failed to load tickets: %s", exc)

        # ── Load edges ──
        for edge_col in EDGE_COLLECTIONS:
            try:
                cursor = db.aql.execute(f"FOR doc IN {edge_col} LIMIT 2000 RETURN doc")
                for doc in cursor:
                    source = doc.get("_from", "")
                    target = doc.get("_to", "")
                    # Only include edges where both nodes exist in our set
                    if source in node_ids and target in node_ids:
                        edges.append({
                            "source": source,
                            "target": target,
                            "type": edge_col,
                        })
            except Exception as exc:
                logger.warning("Failed to load edges %s: %s", edge_col, exc)

    except Exception as exc:
        logger.error("Graph query failed: %s", exc)
        return {"nodes": [], "edges": []}

    logger.info("Graph: %d nodes, %d edges", len(nodes), len(edges))
    return {"nodes": nodes, "edges": edges}


def _extract_node_data(collection: str, doc: dict) -> dict:
    """Extract relevant display data per collection type."""
    if collection == "teams":
        return {
            "name": doc.get("name"),
            "domain": doc.get("domain"),
        }
    if collection == "engineers":
        return {
            "name": doc.get("name"),
            "expertise": doc.get("expertise", []),
            "email": doc.get("email"),
        }
    if collection == "servers":
        return {
            "key": doc.get("_key"),
            "type": doc.get("type"),
            "os": doc.get("os"),
            "datacenter": doc.get("datacenter"),
            "status": doc.get("status"),
        }
    if collection == "services":
        return {
            "key": doc.get("_key"),
            "name": doc.get("name", doc.get("_key")),
            "version": doc.get("version"),
            "port": doc.get("port"),
        }
    if collection == "network_devices":
        return {
            "key": doc.get("_key"),
            "type": doc.get("type"),
            "location": doc.get("location"),
        }
    if collection == "error_codes":
        return {
            "key": doc.get("_key"),
            "message": doc.get("message", ""),
            "severity": doc.get("severity"),
            "service": doc.get("service"),
        }
    return {"key": doc.get("_key")}
