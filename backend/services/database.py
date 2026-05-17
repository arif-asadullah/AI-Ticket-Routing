"""ArangoDB connection helper. Fails gracefully if the database is unavailable."""

import logging
import socket
from urllib.parse import urlparse

from arango import ArangoClient
from arango.database import StandardDatabase

from backend.core.config import settings

logger = logging.getLogger(__name__)

_client: ArangoClient | None = None
_db: StandardDatabase | None = None


def _is_port_open(url: str, timeout: float = 2.0) -> bool:
    """Quick check if the host:port is reachable."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8529
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def connect_arango() -> StandardDatabase | None:
    """Connect to ArangoDB and return a database handle, or None on failure."""
    global _client, _db

    if not _is_port_open(settings.ARANGO_URL):
        logger.warning("ArangoDB unavailable at %s (port not open)", settings.ARANGO_URL)
        return None

    try:
        _client = ArangoClient(
            hosts=settings.ARANGO_URL,
            request_timeout=30,
        )

        # Connect to _system first to ensure the target database exists
        sys_db = _client.db(
            "_system",
            username=settings.ARANGO_USER,
            password=settings.ARANGO_PASSWORD,
        )

        if not sys_db.has_database(settings.ARANGO_DB):
            sys_db.create_database(settings.ARANGO_DB)
            logger.info("Created database '%s'", settings.ARANGO_DB)

        # Now connect to the target database
        _db = _client.db(
            settings.ARANGO_DB,
            username=settings.ARANGO_USER,
            password=settings.ARANGO_PASSWORD,
        )
        _db.version()  # verify connectivity
        logger.info("Connected to ArangoDB at %s (db: %s)", settings.ARANGO_URL, settings.ARANGO_DB)
        return _db
    except Exception as exc:
        logger.warning("ArangoDB unavailable: %s", exc)
        _client = None
        _db = None
        return None


def close_arango() -> None:
    """Close the ArangoDB client connection."""
    global _client, _db
    if _client is not None:
        _client.close()
        logger.info("ArangoDB connection closed")
    _client = None
    _db = None
