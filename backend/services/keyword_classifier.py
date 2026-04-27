"""
Keyword Classifier — Classifier 4 (weight: 0.10)

Counts keyword matches per category. No AI, no database — pure string matching.
Fastest classifier (~1ms). Fallback when everything else is down.
Accuracy: ~55% alone.
"""

KEYWORD_DICT = {
    "Infrastructure": [
        "cpu", "memory", "ram", "disk", "server", "vm", "container", "kubernetes",
        "docker", "restart", "crash", "oom", "kernel", "hardware", "reboot",
        "node", "kubelet", "systemd", "journald", "cgroup", "swap", "uptime",
        "patch", "update", "host", "bare-metal", "hypervisor", "vmware",
    ],
    "Application": [
        "api", "http", "endpoint", "bug", "error", "exception", "timeout",
        "response", "frontend", "backend", "deploy", "version", "500", "503",
        "502", "504", "microservice", "spring", "java", "npm", "build",
        "release", "rollback", "webhook", "grpc", "rest", "jwt", "cors",
    ],
    "Database": [
        "postgres", "postgresql", "mysql", "oracle", "redis", "mongo", "sql",
        "query", "index", "table", "schema", "migration", "replica", "replication",
        "connection pool", "deadlock", "vacuum", "wal", "backup", "dump",
        "etl", "data warehouse", "slow query", "pg_stat",
    ],
    "Network": [
        "ssl", "vpn", "firewall", "dns", "tcp", "udp", "latency", "packet",
        "route", "subnet", "bandwidth", "proxy", "load balancer", "certificate",
        "tls", "bgp", "vlan", "switch", "router", "mtu", "arp", "dhcp",
        "ping", "traceroute", "nslookup",
    ],
    "Security": [
        "authentication", "authorization", "rbac", "token", "encryption",
        "breach", "vulnerability", "malware", "phishing", "audit", "permission",
        "password", "login", "lockout", "mfa", "2fa", "cve", "exploit",
        "intrusion", "access denied", "unauthorized", "sso", "ldap", "active directory",
    ],
    "Storage": [
        "nfs", "san", "nas", "lun", "iscsi", "ceph", "s3", "backup", "snapshot",
        "volume", "mount", "filesystem", "disk full", "quota", "raid",
        "deduplication", "thin provision", "zfs", "lvm", "inode",
        "stale file handle", "archive",
    ],
}


def classify_keyword(text: str) -> dict:
    """
    Count keyword matches per category. Return highest-scoring category.

    Returns:
        {
            "category": "Database",
            "confidence": 0.75,
            "scores": {"Database": 3, "Application": 1, ...}
        }
    """
    text_lower = text.lower()
    scores = {}

    for category, keywords in KEYWORD_DICT.items():
        score = 0
        for kw in keywords:
            if kw in text_lower:
                score += 1
        scores[category] = score

    total = sum(scores.values())
    if total == 0:
        return {"category": None, "confidence": 0.0, "scores": scores}

    winner = max(scores, key=scores.get)
    confidence = scores[winner] / max(total, 1)

    return {
        "category": winner,
        "confidence": round(confidence, 3),
        "scores": scores,
    }
