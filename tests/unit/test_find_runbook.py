"""Unit tests for find_runbook relevance gating.

Locks in the fix for the reported bug where a Security/brute-force ticket was
suggested an unrelated SSL runbook. A runbook is shown ONLY when its title
genuinely overlaps the ticket text; otherwise it is hidden (None).
"""
from backend.services.orchestrator import find_runbook


class _FakeAQL:
    def __init__(self, runbooks):
        self._runbooks = runbooks

    def execute(self, query, bind_vars=None):
        cat = (bind_vars or {}).get("category")
        # Mirrors the AQL projection: { key, title } filtered by category
        return [
            {"key": r["_key"], "title": r["title"]}
            for r in self._runbooks
            if r["category"] == cat
        ]


class _FakeDB:
    def __init__(self, runbooks):
        self.aql = _FakeAQL(runbooks)


# Post-fix categories: SSL is Network, LDAP is Access Management, Security has none.
RUNBOOKS = [
    {"_key": "KB-0003", "title": "VPN connectivity troubleshooting", "category": "Network"},
    {"_key": "KB-0005", "title": "SSL certificate renewal process", "category": "Network"},
    {"_key": "KB-0010", "title": "Firewall rule change procedure", "category": "Network"},
    {"_key": "KB-0006", "title": "LDAP account lockout resolution", "category": "Access Management"},
    {"_key": "KB-0001", "title": "PostgreSQL connection limit exceeded", "category": "Database"},
]


def _db():
    return _FakeDB(RUNBOOKS)


def test_security_bruteforce_hides_runbook():
    # The reported bug: a Security ticket must NOT get the SSL runbook.
    rb = find_runbook(_db(), "Security", None,
                      "Multiple failed login attempts on API Gateway",
                      "credential stuffing, 500 failed logins from foreign IPs")
    assert rb is None


def test_vpn_matches_vpn_runbook():
    rb = find_runbook(_db(), "Network", None,
                      "VPN keeps disconnecting every few minutes",
                      "Cisco AnyConnect drops the connection repeatedly")
    assert rb is not None and rb.startswith("KB-0003")


def test_ssl_matches_ssl_runbook():
    rb = find_runbook(_db(), "Network", None,
                      "SSL certificate expiring in 2 days",
                      "wildcard SSL cert auto-renewal failed")
    assert rb is not None and rb.startswith("KB-0005")


def test_unrelated_network_ticket_hides_runbook():
    # Right category, but no keyword overlap with any Network runbook -> hide.
    rb = find_runbook(_db(), "Network", None,
                      "office printer making a weird noise",
                      "the printer on the 3rd floor is very loud")
    assert rb is None


def test_no_runbooks_for_category_returns_none():
    rb = find_runbook(_db(), "Security", None, "anything", "anything")
    assert rb is None


def test_stopwords_do_not_count_as_a_match():
    # A ticket that only echoes generic filler words ("process", "resolution")
    # must not match a runbook on those words alone.
    rb = find_runbook(_db(), "Network", None,
                      "need help with the process", "what is the resolution procedure")
    assert rb is None


def test_database_connection_matches_postgres_runbook():
    rb = find_runbook(_db(), "Database", None,
                      "PostgreSQL connection pool exhausted",
                      "too many connections, connection limit reached")
    assert rb is not None and rb.startswith("KB-0001")
