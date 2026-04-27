"""
Entity Extractor — Stage 1 of classification pipeline.

Scans ticket text for known server names, service names, and error code patterns.
Results feed into Graph Traversal (Stage 2) and Quality Scorer.

Caches entity lists from ArangoDB on startup. Refreshes every 5 minutes.
"""

import logging
import time
from typing import TypedDict

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes


class ExtractedEntities(TypedDict):
    servers: list[str]
    services: list[str]
    error_codes: list[dict]


class EntityExtractor:
    def __init__(self):
        self._server_keys: list[str] = []
        self._service_keys: list[str] = []
        self._service_names: dict[str, str] = {}  # lowercase name -> _key
        self._error_patterns: list[dict] = []
        self._last_refresh: float = 0

    def refresh_cache(self, db) -> None:
        """Load entity lists from ArangoDB."""
        now = time.time()
        if now - self._last_refresh < CACHE_TTL and self._server_keys:
            return  # cache still valid

        try:
            # Load server keys
            if db.has_collection("servers"):
                self._server_keys = [doc["_key"] for doc in db.collection("servers").all()]

            # Load service keys + names
            if db.has_collection("services"):
                self._service_keys = []
                self._service_names = {}
                for doc in db.collection("services").all():
                    self._service_keys.append(doc["_key"])
                    # Map both _key and name (lowercase) for matching
                    self._service_names[doc["_key"].lower()] = doc["_key"]
                    if doc.get("name"):
                        self._service_names[doc["name"].lower()] = doc["_key"]

            # Load error patterns
            if db.has_collection("error_codes"):
                self._error_patterns = [
                    {
                        "_key": doc["_key"],
                        "pattern": doc["pattern"],
                        "pattern_lower": doc["pattern"].lower(),
                        "service": doc.get("service", ""),
                        "severity": doc.get("severity", "medium"),
                    }
                    for doc in db.collection("error_codes").all()
                ]

            self._last_refresh = now
            logger.info(
                "Entity cache refreshed: %d servers, %d services, %d error patterns",
                len(self._server_keys),
                len(self._service_keys),
                len(self._error_patterns),
            )
        except Exception as exc:
            logger.warning("Failed to refresh entity cache: %s", exc)

    def extract(self, text: str, db=None) -> ExtractedEntities:
        """Extract entities from ticket text."""
        if db:
            self.refresh_cache(db)

        text_lower = text.lower()

        # Match servers
        servers = [s for s in self._server_keys if s.lower() in text_lower]

        # Match services (by key or display name)
        services = []
        seen = set()
        for name_lower, svc_key in self._service_names.items():
            if name_lower in text_lower and svc_key not in seen:
                services.append(svc_key)
                seen.add(svc_key)

        # Match error patterns (full pattern match, not partial)
        error_codes = []
        for err in self._error_patterns:
            if err["pattern_lower"] in text_lower:
                error_codes.append({
                    "error_key": err["_key"],
                    "pattern": err["pattern"],
                    "service": err["service"],
                    "severity": err["severity"],
                })

        return ExtractedEntities(
            servers=servers,
            services=services,
            error_codes=error_codes,
        )


# Module-level singleton
entity_extractor = EntityExtractor()
