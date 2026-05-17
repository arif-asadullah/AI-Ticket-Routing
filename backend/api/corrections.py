"""Corrections API — export training data, recompute centroids, analytics."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import require_admin, require_engineer_or_admin
from backend.services.corrections import get_correction_stats, recompute_centroids
from backend.services.repeated_issues import check_repeated_match, detect_repeated_issues, save_repeated_issues

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


@router.get("/export")
async def export_corrections(
    request: Request,
    user: dict = Depends(require_admin),
    trusted_only: bool = True,
    since: str | None = None,
):
    """Export corrections as training data. Admin only."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    query = """
    FOR c IN corrections
        FILTER (@trusted_only == false OR c.is_trusted == true)
        FILTER (@since == null OR c.created_at >= @since)
        SORT c.created_at ASC
        RETURN {
            ticket_id: c.ticket_id,
            title: c.ticket_title,
            description: c.ticket_description,
            original_category: c.original_category,
            corrected_category: c.corrected_category,
            classifier_votes: c.classifier_votes,
            classifiers_wrong: c.classifiers_wrong,
            classifiers_right: c.classifiers_right,
            reason: c.reason,
            corrected_by: c.corrected_by,
            created_at: c.created_at
        }
    """
    cursor = db.aql.execute(query, bind_vars={
        "trusted_only": trusted_only,
        "since": since,
    })
    return list(cursor)


@router.post("/recompute-centroids")
async def recompute_centroids_endpoint(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Recompute category centroids using corrected ticket categories. Admin only."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    results = recompute_centroids(db)

    # Log to audit trail
    try:
        db.collection("audit_log").insert({
            "ticket_id": None,
            "action": "centroid_recompute",
            "actor": user["email"],
            "old_value": None,
            "new_value": {"categories": results},
            "confidence_score": None,
            "reasoning": f"Centroids recomputed by {user['email']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {"status": "ok", "categories": results}


@router.get("/stats")
async def correction_stats(
    request: Request,
    user: dict = Depends(require_engineer_or_admin),
):
    """Correction analytics — override rate, classifier errors, common misclassifications."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    return get_correction_stats(db)


@router.get("/repeated-issues")
async def get_repeated_issues(
    request: Request,
    user: dict = Depends(require_engineer_or_admin),
):
    """Get detected repeated issue clusters."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    try:
        cursor = db.aql.execute(
            """FOR ri IN repeated_issues
                SORT ri.count DESC
                RETURN UNSET(ri, "center_embedding", "_id", "_rev")"""
        )
        return list(cursor)
    except Exception:
        return []


@router.post("/detect-repeated-issues")
async def run_detection(
    request: Request,
    user: dict = Depends(require_admin),
    days: int = 7,
    min_cluster: int = 3,
):
    """Run repeated issue detection on recent tickets. Admin only."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    clusters = detect_repeated_issues(db, lookback_days=days, min_cluster=min_cluster)
    saved = save_repeated_issues(db, clusters)

    # Log to audit trail
    try:
        db.collection("audit_log").insert({
            "ticket_id": None,
            "action": "repeated_issue_detection",
            "actor": user["email"],
            "old_value": None,
            "new_value": {"clusters_found": saved, "days_scanned": days},
            "confidence_score": None,
            "reasoning": f"Detected {saved} repeated issue clusters in last {days} days",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    # Return clusters without embeddings (too large for response)
    return {
        "status": "ok",
        "clusters_found": saved,
        "clusters": [
            {k: v for k, v in c.items() if k != "center_embedding"}
            for c in clusters
        ],
    }
