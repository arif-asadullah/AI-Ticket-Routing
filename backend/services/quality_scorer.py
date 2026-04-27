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
    Score ticket input quality.

    HIGH:   description > 50 chars AND (has server/service OR has error code)
    MEDIUM: description > 50 chars but no entities or error codes
    LOW:    description < 50 chars, no entities, no errors

    Returns: "HIGH", "MEDIUM", or "LOW"
    """
    desc_len = len(description.strip())
    has_entities = len(entities["servers"]) > 0 or len(entities["services"]) > 0
    has_errors = len(entities["error_codes"]) > 0

    if desc_len > 50 and (has_entities or has_errors):
        return "HIGH"
    elif desc_len > 50:
        return "MEDIUM"
    else:
        return "LOW"


def get_confidence_cap(quality_score: str) -> float:
    """Get the maximum confidence allowed for a quality level."""
    return QUALITY_CAPS.get(quality_score, 0.99)
