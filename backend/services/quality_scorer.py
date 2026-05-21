"""
Quality Scorer — Stage 1 of classification pipeline.

Assesses ticket input quality as HIGH, MEDIUM, or LOW.
Quality score determines maximum confidence allowed:
  HIGH   → confidence up to 0.99
  MEDIUM → confidence capped at 0.85
  LOW    → confidence capped at 0.75 (likely escalated)

Depends on: EntityExtractor (ATR-132) and ErrorScanner (ATR-135)
"""

import logging

from backend.services.entity_extractor import ExtractedEntities

logger = logging.getLogger(__name__)

# Confidence caps per quality level
QUALITY_CAPS = {
    "HIGH": 0.99,
    "MEDIUM": 0.85,
    "LOW": 0.75,
}


def score_quality(
    title: str,
    description: str,
    entities: ExtractedEntities,
) -> str:
    """
    Multi-signal ticket quality scorer.

    Combines 5 signals: entities, error codes, description length,
    technical keywords, and title specificity.

    Returns: "HIGH", "MEDIUM", or "LOW"
    """
    score = 0
    text = f"{title} {description}".strip().lower()
    desc_len = len(description.strip())

    # Signal 1: Has infrastructure entities (strong signal)
    if entities["servers"] or entities["services"]:
        score += 3

    # Signal 2: Has error codes (strong signal)
    if entities["error_codes"]:
        score += 3

    # Signal 3: Description length (diminishing returns)
    if desc_len > 100:
        score += 2
    elif desc_len > 40:
        score += 1

    # Signal 4: Has technical keywords (moderate signal)
    tech_terms = ["error", "fail", "crash", "timeout", "refused", "denied",
                  "down", "slow", "latency", "exception", "500", "503", "oom",
                  "replication", "connection", "memory", "cpu", "disk",
                  "permission", "unauthorized", "certificate", "dns", "vpn"]
    if any(t in text for t in tech_terms):
        score += 1

    # Signal 5: Title specificity (short generic titles = vague)
    if len(title.strip()) > 15:
        score += 1

    # Map score to quality level
    if score >= 5:
        return "HIGH"
    elif score >= 3:
        return "MEDIUM"
    else:
        return "LOW"


def get_confidence_cap(quality_score: str) -> float:
    """Get the maximum confidence allowed for a quality level."""
    return QUALITY_CAPS.get(quality_score, 0.99)
