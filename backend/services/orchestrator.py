"""
Classification Orchestrator — Master controller for the 4-classifier ensemble.

Ties together: Stage 1 (Prepare) → Stage 2 (Retrieve) → Stage 3 (Classify) →
Stage 4 (Aggregate) → Stage 5 (Decide) into one function call.

Handles:
- Health checks (Ollama, ArangoDB data, Redis)
- Degradation level detection (Level 1-4)
- Weight redistribution per level
- Full pipeline execution
- Audit logging

Usage:
    from backend.services.orchestrator import orchestrator
    result = await orchestrator.classify(title, description, db, redis_client)
"""

import logging
import time
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from sentence_transformers import SentenceTransformer

from backend.core.config import settings
from backend.services.aggregator import aggregate
from backend.services.centroid_classifier import classify_centroid
from backend.services.entity_extractor import entity_extractor
from backend.services.error_scanner import errors_confirm_category
from backend.services.keyword_classifier import classify_keyword
from backend.services.knn_classifier import classify_knn
from backend.services.llm_classifier import classify_llm
from backend.services.quality_scorer import score_quality
from backend.services.retrieval import retrieve_all

logger = logging.getLogger(__name__)


class ClassificationResult(TypedDict):
    category: str | None
    secondary_category: str | None
    priority: str
    confidence: float
    agreement: str
    quality_score: str
    classifier_votes: dict
    reasoning: str
    degradation_level: int
    embedding: list[float] | None
    suggested_resolution: list[str] | None
    suggested_runbook: str | None
    recommended_team: str | None
    recommended_expert: str | None
    processing_time_ms: int


class HealthStatus(TypedDict):
    ollama: bool
    db_has_data: bool
    redis: bool
    level: int


# ── Health Check ──

_health_cache: HealthStatus | None = None
_health_cache_time: float = 0
HEALTH_CACHE_TTL = 5  # seconds


async def check_health(db=None, redis_client=None) -> HealthStatus:
    """Check component health. Cached for 5 seconds."""
    global _health_cache, _health_cache_time

    now = time.time()
    if _health_cache and (now - _health_cache_time) < HEALTH_CACHE_TTL:
        return _health_cache

    # Check Ollama
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/version")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    # Check ArangoDB has ticket data
    db_has_data = False
    if db:
        try:
            db_has_data = db.collection("tickets").count() > 0
        except Exception:
            pass

    # Check Redis
    redis_ok = False
    if redis_client:
        try:
            redis_ok = await redis_client.ping()
        except Exception:
            pass

    # Determine level
    if ollama_ok and db_has_data:
        level = 4  # Full
    elif ollama_ok and not db_has_data:
        level = 3  # No data
    elif not ollama_ok and db_has_data:
        level = 2  # No LLM
    else:
        level = 1  # Emergency

    _health_cache = HealthStatus(
        ollama=ollama_ok,
        db_has_data=db_has_data,
        redis=redis_ok,
        level=level,
    )
    _health_cache_time = now

    logger.info("Health check: ollama=%s, db_data=%s, redis=%s → Level %d",
                ollama_ok, db_has_data, redis_ok, level)
    return _health_cache


# ── Embedding Model (singleton) ──

_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Load MiniLM model (cached singleton)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading MiniLM embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


# ── Routing Lookup ──

def lookup_team(db, category: str, priority: str) -> str | None:
    """Look up team from routing_rules."""
    try:
        query = """
        FOR rule IN routing_rules
            FILTER rule.category == @category
            AND rule.priority == @priority
            AND rule.is_active == true
            FOR team IN teams
                FILTER team._key == rule.target_team
                RETURN team.name
        """
        cursor = db.aql.execute(query, bind_vars={"category": category, "priority": priority})
        return next(cursor, None)
    except Exception:
        return None


# ── Main Classification ──

async def classify(
    title: str,
    description: str,
    db=None,
    redis_client=None,
) -> ClassificationResult:
    """
    Full classification pipeline — one function call.

    Stage 1: Prepare (extract entities, quality, embedding)
    Stage 2: Retrieve (4 parallel searches)
    Stage 3: Classify (4 classifiers)
    Stage 4: Aggregate (weighted voting)
    Stage 5: Decide (route or escalate)

    Handles degradation automatically based on component health.
    """
    start = time.time()

    # ── Health Check ──
    health = await check_health(db, redis_client)
    level = health["level"]

    # ── Stage 1: Prepare ──
    entities = entity_extractor.extract(description, db=db) if db else {"servers": [], "services": [], "error_codes": []}
    quality = score_quality(title, description, entities)
    model = get_embedding_model()
    embedding = model.encode(description).tolist()

    # ── Stage 2: Retrieve (skip if no data) ──
    context = None
    if db and health["db_has_data"]:
        context = retrieve_all(db, embedding, entities, description)
    else:
        context = {
            "similar_tickets": [],
            "error_matched_tickets": [],
            "graph_context": None,
            "fulltext_matches": [],
        }

    # ── Stage 3: Classify (based on degradation level) ──
    votes = {}

    # Classifier 1: LLM (skip if Ollama down)
    if health["ollama"]:
        votes["llm"] = await classify_llm(title, description, context)
    else:
        logger.warning("Skipping LLM classifier (Ollama down)")

    # Classifier 2: KNN (skip if no data)
    if health["db_has_data"] and context["similar_tickets"]:
        votes["knn"] = classify_knn(context["similar_tickets"])
    else:
        logger.info("Skipping KNN classifier (no data)")

    # Classifier 3: Centroid (skip if no data)
    if health["db_has_data"] and db:
        votes["centroid"] = classify_centroid(embedding, db=db)
    else:
        logger.info("Skipping Centroid classifier (no data)")

    # Classifier 4: Keywords (always available)
    votes["keyword"] = classify_keyword(description)

    # ── Stage 4: Aggregate ──
    graph_ctx = context.get("graph_context")
    llm_cat = votes.get("llm", {}).get("category")
    graph_confirms = (
        graph_ctx is not None
        and graph_ctx.get("managed_by_domain") == llm_cat
    ) if llm_cat else False

    result = aggregate(
        votes=votes,
        quality_score=quality,
        error_codes=entities["error_codes"],
        graph_confirms_category=graph_confirms,
    )

    # ── Stage 5: Decide + enrich ──
    suggested_resolution = None
    suggested_runbook = None
    recommended_team = None
    recommended_expert = None

    if result["category"] and db:
        # Look up team
        recommended_team = lookup_team(db, result["category"], result["priority"])

        # Best resolution from similar tickets
        if context["similar_tickets"]:
            for t in context["similar_tickets"]:
                if t.get("resolution_steps") and t["category"] == result["category"]:
                    suggested_resolution = t["resolution_steps"]
                    break

        # Best expert from graph
        if graph_ctx and graph_ctx.get("experts"):
            recommended_expert = graph_ctx["experts"][0].get("name")

    elapsed_ms = int((time.time() - start) * 1000)

    logger.info(
        "Classification: %s (%.3f) | level=%d | agreement=%s | %dms",
        result["category"], result["confidence"], level, result["agreement"], elapsed_ms,
    )

    return ClassificationResult(
        category=result["category"],
        secondary_category=result["secondary_category"],
        priority=result["priority"],
        confidence=result["confidence"],
        agreement=result["agreement"],
        quality_score=result["quality_score"],
        classifier_votes=result["classifier_votes"],
        reasoning=result["reasoning"],
        degradation_level=level,
        embedding=embedding,
        suggested_resolution=suggested_resolution,
        suggested_runbook=suggested_runbook,
        recommended_team=recommended_team,
        recommended_expert=recommended_expert,
        processing_time_ms=elapsed_ms,
    )
