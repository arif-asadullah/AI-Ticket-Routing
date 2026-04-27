"""
Hybrid Retrieval — Stage 2 of classification pipeline (ATR-66).

Runs 4 parallel searches to gather context for classification:
  1. Vector similarity search → top 5 similar past tickets
  2. Error code pattern match → past tickets with same error via triggered_by edges
  3. Graph traversal → infrastructure context via edges
  4. Full-text keyword search → matching past tickets via fulltext index

Each method runs independently — one failing doesn't block others.
"""

import logging
from typing import TypedDict

from arango.database import StandardDatabase

from backend.services.entity_extractor import ExtractedEntities

logger = logging.getLogger(__name__)


class SimilarTicket(TypedDict):
    key: str
    title: str
    category: str
    priority: str
    description: str
    similarity: float
    resolution_steps: list[str] | None


class GraphContext(TypedDict):
    server_type: str | None
    server_datacenter: str | None
    managed_by_team: str | None
    managed_by_domain: str | None
    hosted_services: list[str]
    dependent_services: list[str]
    past_tickets_on_server: list[dict]
    experts: list[dict]


class RetrievalResult(TypedDict):
    similar_tickets: list[SimilarTicket]
    error_matched_tickets: list[dict]
    graph_context: GraphContext | None
    fulltext_matches: list[dict]


def search_similar_tickets(db: StandardDatabase, embedding: list[float], limit: int = 5) -> list[SimilarTicket]:
    """Vector similarity search — find top N similar past tickets."""
    try:
        query = """
        FOR ticket IN tickets
            FILTER ticket.status == "closed"
            LET sim = COSINE_SIMILARITY(ticket.embedding, @embedding)
            SORT sim DESC
            LIMIT @limit
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
                resolution_steps: resolution.steps
            }
        """
        cursor = db.aql.execute(query, bind_vars={"embedding": embedding, "limit": limit})
        results = list(cursor)
        logger.info("Vector search: found %d similar tickets", len(results))
        return results
    except Exception as exc:
        logger.warning("Vector search failed: %s", exc)
        return []


def search_by_error_codes(db: StandardDatabase, error_codes: list[dict]) -> list[dict]:
    """Find past tickets with the same error codes via triggered_by edges."""
    if not error_codes:
        return []

    try:
        all_matches = []
        for err in error_codes:
            query = """
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
            """
            cursor = db.aql.execute(query, bind_vars={"error_key": err["error_key"]})
            matches = list(cursor)
            all_matches.extend(matches)

        # Deduplicate by ticket key
        seen = set()
        unique = []
        for m in all_matches:
            if m["key"] not in seen:
                seen.add(m["key"])
                unique.append(m)

        logger.info("Error match: found %d tickets for %d error codes", len(unique), len(error_codes))
        return unique
    except Exception as exc:
        logger.warning("Error code search failed: %s", exc)
        return []


def traverse_graph(db: StandardDatabase, entities: ExtractedEntities) -> GraphContext | None:
    """Graph traversal — find infrastructure context from extracted entities."""
    if not entities["servers"] and not entities["services"]:
        return None

    try:
        context = GraphContext(
            server_type=None,
            server_datacenter=None,
            managed_by_team=None,
            managed_by_domain=None,
            hosted_services=[],
            dependent_services=[],
            past_tickets_on_server=[],
            experts=[],
        )

        # Use first server for traversal
        server_key = entities["servers"][0] if entities["servers"] else None

        if server_key:
            # Get server details + hosted services + managing team
            query = """
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
            """
            cursor = db.aql.execute(query, bind_vars={"server_key": server_key})
            result = next(cursor, None)

            if result:
                context["server_type"] = result.get("server_type")
                context["server_datacenter"] = result.get("server_datacenter")
                context["managed_by_team"] = result.get("team_name")
                context["managed_by_domain"] = result.get("team_domain")
                context["hosted_services"] = result.get("services", [])
                context["past_tickets_on_server"] = result.get("past_tickets", [])
                context["experts"] = result.get("experts", [])

        # Check service dependencies
        for svc_key in entities["services"][:2]:  # max 2 to avoid slow queries
            try:
                query = """
                FOR dep IN 1..1 INBOUND CONCAT("services/", @svc_key) depends_on
                    RETURN dep.name
                """
                cursor = db.aql.execute(query, bind_vars={"svc_key": svc_key})
                context["dependent_services"].extend(list(cursor))
            except Exception:
                pass

        logger.info(
            "Graph traversal: server=%s, team=%s, past_tickets=%d, experts=%d",
            server_key,
            context["managed_by_team"],
            len(context["past_tickets_on_server"]),
            len(context["experts"]),
        )
        return context
    except Exception as exc:
        logger.warning("Graph traversal failed: %s", exc)
        return None


def search_fulltext(db: StandardDatabase, text: str, limit: int = 5) -> list[dict]:
    """Full-text keyword search on ticket title and description."""
    try:
        # Extract meaningful keywords (skip short/common words)
        words = [w for w in text.lower().split() if len(w) > 3]
        if not words:
            return []

        # Use first 5 significant words
        search_terms = words[:5]

        # ArangoDB fulltext search
        results = []
        for term in search_terms:
            try:
                query = """
                FOR doc IN FULLTEXT(tickets, "description", @term)
                    FILTER doc.status == "closed"
                    LIMIT @limit
                    RETURN {
                        key: doc._key,
                        title: doc.title,
                        category: doc.category,
                        description: LEFT(doc.description, 150)
                    }
                """
                cursor = db.aql.execute(query, bind_vars={"term": term, "limit": limit})
                results.extend(list(cursor))
            except Exception:
                pass

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["key"] not in seen:
                seen.add(r["key"])
                unique.append(r)

        logger.info("Fulltext search: found %d matches for %d terms", len(unique), len(search_terms))
        return unique[:limit]
    except Exception as exc:
        logger.warning("Fulltext search failed: %s", exc)
        return []


def retrieve_all(
    db: StandardDatabase,
    embedding: list[float],
    entities: ExtractedEntities,
    description: str,
) -> RetrievalResult:
    """
    Run all 4 retrieval methods and return combined context.

    In production, these should run via asyncio.gather() for parallel execution.
    For now, sequential is fine — total time ~50-100ms.
    """
    similar = search_similar_tickets(db, embedding)
    error_matches = search_by_error_codes(db, entities["error_codes"])
    graph = traverse_graph(db, entities)
    fulltext = search_fulltext(db, description)

    return RetrievalResult(
        similar_tickets=similar,
        error_matched_tickets=error_matches,
        graph_context=graph,
        fulltext_matches=fulltext,
    )
