"""Unit tests for find_runbook relevance gating.

Locks in the fix for the reported bug where a Security/brute-force ticket was
suggested an unrelated SSL runbook. A runbook is shown ONLY when its title
genuinely overlaps the ticket's own title/description; otherwise it is hidden
(None). The suggested resolution's wording is deliberately NOT scored —
resolutions are ranked by effectiveness without a relevance floor, so an
off-topic resolution must not drag in an off-topic runbook.
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
    {"_key": "KB-0004", "title": "Kubernetes pod OOMKilled recovery", "category": "Infrastructure"},
]


def _db():
    return _FakeDB(RUNBOOKS)


def test_security_bruteforce_hides_runbook():
    # The reported bug: a Security ticket must NOT get the SSL runbook.
    rb = find_runbook(_db(), "Security",
                      "Multiple failed login attempts on API Gateway",
                      "credential stuffing, 500 failed logins from foreign IPs")
    assert rb is None


def test_vpn_matches_vpn_runbook():
    rb = find_runbook(_db(), "Network",
                      "VPN keeps disconnecting every few minutes",
                      "Cisco AnyConnect drops the connection repeatedly")
    assert rb is not None and rb.startswith("KB-0003")


def test_ssl_matches_ssl_runbook():
    rb = find_runbook(_db(), "Network",
                      "SSL certificate expiring in 2 days",
                      "wildcard SSL cert auto-renewal failed")
    assert rb is not None and rb.startswith("KB-0005")


def test_unrelated_network_ticket_hides_runbook():
    # Right category, but no keyword overlap with any Network runbook -> hide.
    rb = find_runbook(_db(), "Network",
                      "office printer making a weird noise",
                      "the printer on the 3rd floor is very loud")
    assert rb is None


def test_no_runbooks_for_category_returns_none():
    rb = find_runbook(_db(), "Security", "anything", "anything")
    assert rb is None


def test_stopwords_do_not_count_as_a_match():
    # A ticket that only echoes generic filler words ("process", "resolution")
    # must not match a runbook on those words alone.
    rb = find_runbook(_db(), "Network",
                      "need help with the process", "what is the resolution procedure")
    assert rb is None


def test_database_connection_matches_postgres_runbook():
    rb = find_runbook(_db(), "Database",
                      "PostgreSQL connection pool exhausted",
                      "too many connections, connection limit reached")
    assert rb is not None and rb.startswith("KB-0001")


def test_resolution_wording_cannot_drag_in_a_runbook():
    # Regression for the 2026-06-12 re-run finding: "Quantum flux capacitor"
    # (Infrastructure, no real overlap) got KB-0004 because its irrelevant
    # suggested *resolution* mentioned kubernetes/pods. Relevance is now scored
    # against the ticket's own text only — this ticket must get NO runbook,
    # regardless of what any suggested resolution says.
    rb = find_runbook(_db(), "Infrastructure",
                      "Quantum flux capacitor misaligned",
                      "The quantum flux capacitor in building 7 is misaligned and the warp coils are overheating.")
    assert rb is None


def test_oomkilled_ticket_still_matches_k8s_runbook():
    # The positive side of the same boundary: a genuinely K8s ticket still gets KB-0004.
    rb = find_runbook(_db(), "Infrastructure",
                      "Kubernetes pod OOMKilled during deployment",
                      "payment-service pod keeps getting OOMKilled on the prod cluster")
    assert rb is not None and rb.startswith("KB-0004")
