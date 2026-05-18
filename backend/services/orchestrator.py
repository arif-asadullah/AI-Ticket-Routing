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

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from sentence_transformers import SentenceTransformer

from backend.core.config import settings
from backend.services.aggregator import aggregate
from backend.services.cache import cache_get, cache_set
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
    resolution_effectiveness: float | None
    suggested_runbook: str | None
    recommended_team: str | None
    recommended_expert: str | None
    processing_time_ms: int
    cache_tier: str | None  # "A", "B", or None (miss)
    enrichment: dict | None  # Enrichment questions for vague tickets


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

def find_runbook(db, category: str, resolution_steps: list[str] | None) -> str | None:
    """Find the most relevant runbook for this category."""
    try:
        # First: try to find runbook matching category
        query = """
        FOR rb IN runbooks
            FILTER rb.category == @category
            RETURN { key: rb._key, title: rb.title }
        """
        cursor = db.aql.execute(query, bind_vars={"category": category})
        runbooks = list(cursor)

        if not runbooks:
            return None

        # If only one, return it
        if len(runbooks) == 1:
            return f"{runbooks[0]['key']}: {runbooks[0]['title']}"

        # If multiple, try to match by resolution text
        if resolution_steps:
            res_text = " ".join(resolution_steps).lower()
            for rb in runbooks:
                # Check if runbook title keywords appear in resolution
                title_words = rb["title"].lower().split()
                matches = sum(1 for w in title_words if w in res_text)
                if matches >= 2:
                    return f"{rb['key']}: {rb['title']}"

        # Default to first matching runbook
        return f"{runbooks[0]['key']}: {runbooks[0]['title']}"
    except Exception:
        return None


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
    user_email: str | None = None,
    skip_cache: bool = False,
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

    # ── Cache Check: Tier A (exact text match) ──
    if skip_cache:
        cached, tier = None, "miss"
    else:
        cached, tier = await cache_get(redis_client, title, description)
    if cached is not None:
        elapsed_ms = int((time.time() - start) * 1000)
        cached["processing_time_ms"] = elapsed_ms
        cached["cache_tier"] = tier
        logger.info("Cache HIT (Tier %s) in %dms: %s", tier, elapsed_ms, cached.get("category"))
        return ClassificationResult(**cached)

    # ── Health Check ──
    health = await check_health(db, redis_client)
    level = health["level"]

    # ── Stage 1: Prepare ──
    entities = entity_extractor.extract(description, db=db) if db else {"servers": [], "services": [], "error_codes": []}
    quality = score_quality(title, description, entities)
    model = get_embedding_model()
    embedding = model.encode(description).tolist()

    # ── Cache Check: Tier B (semantic similarity — needs embedding) ──
    if skip_cache:
        cached, tier = None, "miss"
    else:
        cached, tier = await cache_get(redis_client, title, description, embedding=embedding)
    if cached is not None:
        elapsed_ms = int((time.time() - start) * 1000)
        cached["processing_time_ms"] = elapsed_ms
        cached["cache_tier"] = tier
        cached["embedding"] = embedding
        logger.info("Cache HIT (Tier %s) in %dms: %s", tier, elapsed_ms, cached.get("category"))
        return ClassificationResult(**cached)

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

    # ── Stage 3: Classify (parallel execution — ATR-76) ──
    # Run all available classifiers concurrently using asyncio.gather().
    # LLM takes ~2-5s, others take <10ms — parallel = total time ≈ LLM time only.
    votes = {}
    tasks = {}

    # Classifier 1: LLM (skip if Ollama down or circuit breaker open)
    from backend.services.circuit_breaker import ollama_breaker
    if health["ollama"] and ollama_breaker.is_available:
        tasks["llm"] = classify_llm(title, description, context)
    else:
        reason = "Ollama down" if not health["ollama"] else f"circuit breaker {ollama_breaker.state.value}"
        logger.warning("Skipping LLM classifier (%s)", reason)

    # Classifiers 2-4: sync functions wrapped as coroutines to run in parallel with LLM
    async def run_knn():
        if health["db_has_data"] and context["similar_tickets"]:
            return classify_knn(context["similar_tickets"])
        logger.info("Skipping KNN classifier (no data)")
        return None

    async def run_centroid():
        if health["db_has_data"] and db:
            return classify_centroid(embedding, db=db)
        logger.info("Skipping Centroid classifier (no data)")
        return None

    async def run_keyword():
        return classify_keyword(description)

    tasks["knn"] = run_knn()
    tasks["centroid"] = run_centroid()
    tasks["keyword"] = run_keyword()

    # Run all classifiers in parallel
    task_names = list(tasks.keys())
    results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for name, result in zip(task_names, results_list):
        if isinstance(result, Exception):
            logger.warning("Classifier %s failed: %s", name, result)
        elif result is not None:
            votes[name] = result

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
    resolution_effectiveness = None
    suggested_runbook = None
    recommended_team = None
    recommended_expert = None

    if result["category"] and db:
        # Look up team
        recommended_team = lookup_team(db, result["category"], result["priority"])

        # Best resolution — check multiple sources, pick highest effectiveness
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

        # Find matching runbook
        suggested_runbook = find_runbook(db, result["category"], suggested_resolution)

        # Best expert from graph
        if graph_ctx and graph_ctx.get("experts"):
            recommended_expert = graph_ctx["experts"][0].get("name")

    elapsed_ms = int((time.time() - start) * 1000)

    # ── Enrichment Agent (for vague tickets) ──
    enrichment = None
    try:
        from backend.services.enrichment_agent import generate_enrichment
        enrichment = generate_enrichment(
            title, description, quality, result["confidence"],
            user_email, entities, embedding, db,
        )
        if enrichment:
            logger.info("Enrichment needed: %s", enrichment["reason"])
    except Exception as exc:
        logger.warning("Enrichment agent failed: %s", exc)

    logger.info(
        "Classification: %s (%.3f) | level=%d | agreement=%s | %dms",
        result["category"], result["confidence"], level, result["agreement"], elapsed_ms,
    )

    final = ClassificationResult(
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
        resolution_effectiveness=resolution_effectiveness,
        suggested_runbook=suggested_runbook,
        recommended_team=recommended_team,
        recommended_expert=recommended_expert,
        processing_time_ms=elapsed_ms,
        cache_tier=None,
        enrichment=enrichment,
    )

    # ── Cache Write (both tiers) ──
    await cache_set(redis_client, title, description, embedding, dict(final))

    return final
