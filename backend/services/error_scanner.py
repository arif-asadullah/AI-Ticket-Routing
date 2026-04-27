"""
Error Code Scanner — Stage 1 of classification pipeline.

Scans ticket text for known error patterns from error_codes collection.
Uses the EntityExtractor's error matching internally.

This is a thin wrapper that provides a focused API for error-specific logic:
- Returns matched errors with severity and service
- Used by Quality Scorer (has_error = HIGH quality)
- Used by Aggregator (error_code_confirms = +0.03 confidence bonus)
- Used by Stage 2 retrieval (triggered_by edge traversal)
"""

import logging
from typing import TypedDict

from backend.services.entity_extractor import entity_extractor

logger = logging.getLogger(__name__)


class ErrorMatch(TypedDict):
    error_key: str
    pattern: str
    service: str
    severity: str


def scan_errors(text: str, db=None) -> list[ErrorMatch]:
    """
    Scan ticket text for known error patterns.

    Returns list of matched errors with their severity and associated service.
    Empty list if no matches found.
    """
    entities = entity_extractor.extract(text, db=db)
    return entities["error_codes"]


def get_highest_severity(errors: list[ErrorMatch]) -> str | None:
    """Get the highest severity from matched errors."""
    if not errors:
        return None

    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return max(errors, key=lambda e: severity_order.get(e["severity"], 0))["severity"]


def errors_confirm_category(errors: list[ErrorMatch], category: str) -> bool:
    """
    Check if matched error codes confirm the classified category.

    Maps error service to category:
      postgresql, redis → Database
      nginx, order-service, auth-service → Application
      kubernetes, linux → Infrastructure
      firewall, vpn, dns → Network
      active-directory, api-gateway → Security
      nfs → Storage
    """
    service_to_category = {
        "postgresql": "Database",
        "redis": "Database",
        "nginx": "Application",
        "order-service": "Application",
        "auth-service": "Application",
        "kubernetes": "Infrastructure",
        "linux": "Infrastructure",
        "firewall": "Network",
        "vpn": "Network",
        "dns": "Network",
        "active-directory": "Security",
        "api-gateway": "Security",
        "nfs": "Storage",
    }

    for err in errors:
        err_category = service_to_category.get(err["service"])
        if err_category == category:
            return True

    return False
