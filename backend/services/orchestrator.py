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
import re
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
    ai_generated_resolution: dict | None  # LLM-generated resolution steps
    automation_suggestion: dict | None  # Repeated-issue automation recommendation
    learned_from_correction: dict | None  # Set when a human-correction precedent was applied


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


def preprocess_text(title: str, description: str) -> str:
    """Clean text before embedding — remove noise, keep signal."""
    text = f"{title}. {description}"
    # Remove timestamps (ISO, syslog, etc.)
    text = re.sub(r'\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}[.\dZ]*', '', text)
    # Replace IP addresses with token (noise for category classification)
    text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP_ADDR', text)
    # Remove UUIDs
    text = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '', text, flags=re.I)
    # Remove long file paths (keep filename only)
    text = re.sub(r'(/[\w.-]+){3,}/', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate to ~512 tokens (roughly 2000 chars) to avoid embedding dilution
    return text[:2000]


# ── Routing Lookup ──

# Generic words in runbook titles that should NOT count as a content match
# (otherwise filler like "process"/"resolution" causes false runbook suggestions).
_RUNBOOK_STOPWORDS = {
    "process", "resolution", "troubleshooting", "recovery",
    "management", "procedure", "issue", "error", "guide", "steps",
}


def find_runbook(db, category: str,
                 title: str | None = None, description: str | None = None) -> str | None:
    """Return a runbook ONLY if it genuinely matches the ticket; otherwise None (hide it).

    A wrong/cross-topic runbook is worse than none, so we require real keyword
    overlap between the runbook's title and the ticket text rather than blindly
    defaulting to the first runbook of the category.

    Relevance is scored against the ticket's own title + description ONLY —
    never the suggested resolution. Resolutions are ranked by effectiveness
    without a relevance floor, so an off-topic resolution's wording would
    otherwise drag in an equally off-topic runbook.
    """
    try:
        # Candidate runbooks for this category
        query = """
        FOR rb IN runbooks
            FILTER rb.category == @category
            RETURN { key: rb._key, title: rb.title }
        """
        cursor = db.aql.execute(query, bind_vars={"category": category})
        runbooks = list(cursor)

        if not runbooks:
            return None

        # Build the ticket text we score relevance against
        query_text = f"{title or ''} {description or ''}".lower()

        # Score each candidate by meaningful title-word overlap with the ticket text
        best_rb, best_score = None, 0
        for rb in runbooks:
            title_words = {
                w for w in re.findall(r"[a-z0-9]+", (rb["title"] or "").lower())
                if len(w) >= 3 and not w.isdigit() and w not in _RUNBOOK_STOPWORDS
            }
            score = sum(1 for w in title_words if w in query_text)
            if score > best_score:
                best_rb, best_score = rb, score

        # Only show a runbook if it's a genuine content match; otherwise hide it.
        if best_rb and best_score >= 1:
            return f"{best_rb['key']}: {best_rb['title']}"
        return None
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
    use_correction_precedent: bool = True,
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
    # Offload blocking DB/CPU work onto worker threads so the async event loop
    # stays free to service other requests (entity extract + embedding are the
    # heaviest synchronous steps).
    if db:
        entities = await asyncio.to_thread(entity_extractor.extract, description, db=db)
    else:
        entities = {"servers": [], "services": [], "error_codes": []}
    quality = score_quality(title, description, entities)
    model = get_embedding_model()
    embedding = await asyncio.to_thread(
        lambda: model.encode(preprocess_text(title, description)).tolist()
    )

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
        context = await asyncio.to_thread(retrieve_all, db, embedding, entities, description)
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
            return await asyncio.to_thread(classify_centroid, embedding, db)
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

    # ── Stage 4.5: Honor human-corrected precedent (reliable self-learning) ──
    # If a TRUSTED, near-identical past correction exists, adopt its category.
    # Exact cosine over the small corrections set is deterministic — unlike the
    # approximate ANN that KNN relies on — so a human override reliably teaches
    # the system for near-identical future tickets. Forced OFF during evaluation
    # (use_correction_precedent=False) so the benchmark stays a pure classifier
    # measurement. Fail-safe: any error here is a no-op; classification proceeds.
    learned_from_correction = None
    if (
        use_correction_precedent
        and settings.CORRECTION_PRECEDENT_ENABLED
        and db
        and embedding
        and result["category"]
    ):
        try:
            from backend.services.corrections import find_correction_precedent
            precedent = await asyncio.to_thread(find_correction_precedent, db, embedding)
            if precedent and precedent["category"] and precedent["category"] != result["category"]:
                logger.info(
                    "Correction precedent applied: %s → %s (sim %.3f, from ticket %s)",
                    result["category"], precedent["category"],
                    precedent["similarity"], precedent.get("ticket_id"),
                )
                learned_from_correction = {
                    "from_category": result["category"],
                    "to_category": precedent["category"],
                    "similarity": round(precedent["similarity"], 3),
                    "precedent_ticket_id": precedent.get("ticket_id"),
                    "precedent_title": precedent.get("title"),
                    "reason": precedent.get("reason"),
                    "corrected_by": precedent.get("corrected_by"),
                }
                result["secondary_category"] = result["category"]
                result["category"] = precedent["category"]
                result["confidence"] = max(result.get("confidence", 0.0), 0.90)
                result["reasoning"] = (
                    f"Applied a verified human correction from a near-identical past "
                    f"ticket (similarity {precedent['similarity']:.0%}) → reclassified to "
                    f"{precedent['category']}. " + (result.get("reasoning") or "")
                )
        except Exception as exc:
            logger.warning("Correction-precedent step failed (ignored): %s", exc)

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

        # Minimum similarity for a past ticket's resolution to be considered relevant.
        # Without this, the highest-effectiveness same-category resolution was used
        # regardless of topic (e.g. an email ticket getting a Kubernetes fix).
        RES_SIM_THRESHOLD = 0.55

        # Source 1: similar past tickets (same category). similar_tickets are already
        # re-ranked by relevance (similarity + recency + effectiveness), so take the
        # FIRST genuinely-similar match rather than the globally highest-effectiveness
        # one — this keeps the suggested fix topically on-point.
        if context["similar_tickets"]:
            for t in context["similar_tickets"]:
                if not t.get("resolution_steps") or t.get("category") != result["category"]:
                    continue
                if (t.get("similarity") or 0) < RES_SIM_THRESHOLD:
                    continue  # too dissimilar — would be an irrelevant resolution
                suggested_resolution = t["resolution_steps"]
                resolution_effectiveness = t.get("effectiveness") or 0.8
                best_effectiveness = resolution_effectiveness
                break

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
        suggested_runbook = find_runbook(db, result["category"], title, description)

        # Best expert from graph
        if graph_ctx and graph_ctx.get("experts"):
            recommended_expert = graph_ctx["experts"][0].get("name")

    # ── AI Resolution Generator (when no good historical resolution) ──
    # AI resolution generation is a SECOND LLM call. By default it's kept off the
    # critical path (settings.GENERATE_RESOLUTION_INLINE = False) so create-ticket
    # latency is a single LLM round-trip; the historical/retrieved resolution is
    # still attached. Flip the flag to generate inline.
    ai_generated_resolution = None
    if result["category"] and health["ollama"] and settings.GENERATE_RESOLUTION_INLINE:
        should_generate = (
            (not suggested_resolution or (resolution_effectiveness or 0) < 0.5)
            and result["confidence"] >= 0.60
        )
        if should_generate:
            try:
                from backend.services.resolution_generator import generate_resolution
                ai_generated_resolution = await generate_resolution(
                    title, description, result["category"], result["priority"],
                    entities, context.get("similar_tickets", []),
                    graph_ctx, entities["error_codes"],
                )
                if ai_generated_resolution:
                    # Use AI steps as suggested resolution if we had none
                    if not suggested_resolution:
                        suggested_resolution = ai_generated_resolution["steps"]
                    logger.info("AI resolution generated: %d steps", len(ai_generated_resolution["steps"]))
            except Exception as exc:
                logger.warning("AI resolution generator failed: %s", exc)

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

    # ── Agentic: repeated-issue detection → automation suggestion ──
    # If this ticket matches a known recurring cluster, recommend automating it
    # (closes the "detect repeated issue -> suggest automation" agentic loop).
    automation_suggestion = None
    if db and embedding:
        try:
            from backend.services.repeated_issues import check_repeated_match
            match = check_repeated_match(db, embedding)
            if match:
                action = (
                    f"auto-apply runbook {suggested_runbook}"
                    if suggested_runbook else
                    f"create a remediation runbook for {result['category']}"
                )
                automation_suggestion = {
                    "is_repeated": True,
                    "cluster_id": match["cluster_id"],
                    "occurrences": match["count"],
                    "representative": match["representative_title"],
                    "category": match["category"],
                    "similarity": match["similarity"],
                    "suggestion": (
                        f"This matches a recurring issue seen {match['count']} times "
                        f"(\"{match['representative_title']}\"). Suggested automation: {action}, "
                        f"and add an alert rule so future occurrences are auto-remediated or fast-tracked."
                    ),
                }
                logger.info("Repeated-issue match: %s (x%d)", match["cluster_id"], match["count"])
        except Exception as exc:
            logger.warning("Repeated-issue check failed: %s", exc)

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
        ai_generated_resolution=ai_generated_resolution,
        automation_suggestion=automation_suggestion,
        learned_from_correction=learned_from_correction,
    )

    # ── Cache Write (both tiers) ──
    await cache_set(redis_client, title, description, embedding, dict(final))

    return final
