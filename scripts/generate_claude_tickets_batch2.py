#!/usr/bin/env python3
"""Generate batch 2 of Claude tickets — 101 more unique tickets."""

import json
import random
from pathlib import Path

random.seed(101)
OUTPUT_FILE = Path("data/synthetic/strategy1_multimodel/claude_tickets.json")

RUNBOOKS = ["KB-0001","KB-0002","KB-0003","KB-0004","KB-0005","KB-0006","KB-0007","KB-0008","KB-0009","KB-0010",None,None,None,None]

def t(title, desc, cat, pri, servers, services, errors, runbook, persona, secondary=None, steps=None):
    return {
        "title": title,
        "description": desc,
        "category": cat,
        "priority": pri,
        "affects_servers": servers,
        "affects_services": services,
        "error_codes": errors,
        "resolution_steps": steps or ["Investigated issue", "Identified root cause", "Applied fix", "Verified resolution"],
        "resolution_effectiveness": round(random.uniform(0.75, 0.95), 2),
        "references_runbook": runbook,
        "quality_score": "HIGH",
        "secondary_category": secondary,
        "classifier_votes": None,
        "source_model": "claude",
        "persona": persona,
    }

tickets = [
    # ── FRUSTRATED USER (34 tickets) ──
    # Infrastructure (6)
    t("computer wont turn on", "my desktop wont power on at all. tried different power outlets same thing. other computers on my desk are fine. need to work on quarterly presentation thats due tomorrow", "Infrastructure", "high", [], [], [], None, "frustrated_user"),
    t("updates taking FOREVER", "windows update has been running for 3 hours now. stuck at 78%. cant use my computer at all. was in the middle of important work when it started. didnt even ask to update!!!", "Infrastructure", "medium", ["prod-app-02"], [], [], None, "frustrated_user"),
    t("fan noise super loud on server rack", "walked past the server room and one of the servers sounds like a jet engine. fan is crazy loud. not sure which one. should someone check before it breaks?", "Infrastructure", "medium", ["prod-k8s-node-01"], [], [], None, "frustrated_user"),
    t("citrix session keeps disconnecting", "every time i open citrix it connects for like 5 minutes then drops. have to login again and again. happening from home and office. been 4 days now nobody has fixed it", "Infrastructure", "high", ["prod-app-01"], [], [], None, "frustrated_user"),
    t("server migration broke everything", "after that server migration over the weekend nothing works right. apps are slow, files are missing, printer doesnt work. did anyone test this before going live??", "Infrastructure", "high", ["prod-app-03"], ["order-service"], [], None, "frustrated_user"),
    t("out of office not working", "set my out of office reply but people keep saying they didnt get it. checked settings multiple times its definitely on. tried removing and re-adding. nothing works", "Infrastructure", "low", ["prod-mail-01"], ["exchange"], [], None, "frustrated_user"),

    # Application (6)
    t("app freezes when i click save", "the inventory app freezes completely when i try to save changes. have to force close and start over. losing all my work every time. happened 6 times today already", "Application", "high", ["prod-app-01"], ["order-service"], [], None, "frustrated_user"),
    t("login page shows blank white screen", "the company portal login page is just blank. no fields no buttons nothing. cleared cache cookies everything still blank. tried chrome firefox edge all same", "Application", "high", ["prod-web-01"], ["nginx", "auth-service"], [], None, "frustrated_user"),
    t("mobile app crashing on android", "our company mobile app crashes immediately when i open it. worked fine yesterday. tried uninstalling and reinstalling. other people in my team also crashing. iphone users seem fine tho", "Application", "high", ["prod-app-02"], ["api-gateway"], [], None, "frustrated_user"),
    t("report downloads as blank pdf", "trying to download the monthly sales report but the PDF is completely blank. tried different report dates same thing. the preview on screen looks fine but download is blank", "Application", "medium", ["prod-app-01"], ["order-service"], [], None, "frustrated_user"),
    t("SPELL CHECK NOT WORKING in email", "spellcheck in outlook stopped working. sending emails with typos to clients which is embarrassing. tried enabling it in settings but the option is greyed out", "Application", "low", ["prod-mail-01"], ["exchange"], [], None, "frustrated_user"),
    t("notification spam from system", "getting like 50 notification emails per hour from the ticketing system. tried unsubscribing but they keep coming. my inbox is completely unusable. MAKE IT STOP", "Application", "medium", ["prod-app-03"], ["order-service"], [], None, "frustrated_user"),

    # Database (5)
    t("customer lookup returns wrong person", "when i search for a customer by phone number it shows a completely different person's info. this is a MAJOR problem — we could expose private data. happened 3 times today", "Database", "critical", ["prod-db-01"], ["postgresql"], [], None, "frustrated_user"),
    t("inventory count showing negative numbers", "the inventory system shows -47 units for product SKU-8842. how can we have negative inventory?? the warehouse says they have 200 units. system is wrong", "Database", "high", ["prod-db-01"], ["postgresql"], [], None, "frustrated_user"),
    t("old deleted records coming back", "records i deleted last week are reappearing in the system. deleted customer complaints showing up again in the queue. feels like the database is haunted or something", "Database", "medium", ["prod-db-02"], ["postgresql"], [], None, "frustrated_user"),
    t("export to excel broken", "trying to export our customer list to excel and it either times out or gives an error. list has about 50,000 records. used to work fine last month. need this for marketing campaign", "Database", "medium", ["prod-db-01"], ["postgresql"], ["ERR-PG-001"], "KB-0001", "frustrated_user"),
    t("duplicate entries everywhere", "the system is creating duplicate records for everything. same customer appears 3 times. same order shows up twice. data cleanup is going to be a nightmare. what happened??", "Database", "high", ["prod-db-01"], ["postgresql"], [], None, "frustrated_user"),

    # Network (5)
    t("skype calls have terrible echo", "every skype call i make has a terrible echo. people can hear themselves talking back. tried different headset same issue. only happens on company network not on mobile data", "Network", "medium", [], [], [], None, "frustrated_user"),
    t("certain websites blocked that shouldnt be", "our content management tool website is being blocked by the firewall. it says 'access denied by corporate policy'. this is a legitimate work tool we use every day. who blocked it??", "Network", "medium", [], [], ["ERR-FW-001"], "KB-0010", "frustrated_user"),
    t("remote desktop super laggy", "remote desktop to my office computer is unusably slow. like 5 second delay on every click. was fine last week. internet speed test shows 100mbps so its not my connection", "Network", "high", [], [], [], None, "frustrated_user"),
    t("printers not found on new wifi", "after the wifi upgrade last weekend none of the printers show up anymore. cant print from any computer on the floor. IT said new wifi was 'better' but now nothing works", "Network", "medium", [], [], [], None, "frustrated_user"),
    t("video conferencing keeps buffering", "teams/zoom calls buffer every 30 seconds. freezes then catches up. everyone in the Mumbai office has the same problem. started after the network maintenance on saturday", "Network", "high", [], [], [], None, "frustrated_user"),

    # Security (5)
    t("locked out of EVERYTHING after vacation", "came back from 2 weeks vacation and now i cant login to anything. password expired? account deactivated?? i wasnt told about any changes. stuck sitting at my desk doing nothing", "Security", "high", ["prod-ldap-01"], ["active-directory"], ["ERR-AUTH-001"], "KB-0009", "frustrated_user"),
    t("random 2FA codes on my phone", "keep getting 2FA authentication codes on my phone that i didnt request. like 5 in the last hour. is someone trying to hack my account??? very concerned", "Security", "critical", ["prod-ldap-01"], ["active-directory"], ["ERR-SEC-001"], None, "frustrated_user"),
    t("browser keeps warning about unsafe site", "chrome shows 'your connection to this site is not private' for our internal HR portal. wont let me access payroll info. tried other browsers same warning", "Security", "high", [], ["api-gateway"], ["ERR-SSL-001"], "KB-0005", "frustrated_user"),
    t("someone changed my email signature", "my email signature was changed to something weird. i didnt do it. worried someone has access to my outlook. please investigate and change my password", "Security", "high", ["prod-mail-01"], ["exchange"], [], None, "frustrated_user"),
    t("USB drive not working — security blocked?", "plugged in my USB drive to copy files for a presentation and nothing happens. tried 3 different USB ports. colleague says USB was disabled for security. how am i supposed to present to client tomorrow??", "Security", "medium", [], [], [], None, "frustrated_user"),

    # Storage (4)
    t("cant attach files to email — too large", "trying to email a 30mb presentation to a client but it keeps bouncing back saying too large. this is a normal business file why is there such a small limit?? tried compressing it still too big", "Storage", "medium", ["prod-mail-01"], ["exchange"], [], None, "frustrated_user"),
    t("mapped network drive disappeared", "my Z: drive that maps to the shared department folder just disappeared from my computer. tried mapping it again but 'network path not found'. all my project files are there!!!", "Storage", "high", ["prod-nfs-01"], ["nfs"], ["ERR-NFS-001"], "KB-0006", "frustrated_user"),
    t("recycle bin empty but disk still full", "my computer says disk full but i emptied the recycle bin and deleted everything i could. still says 2% free. where is all the space going?? cant even save documents", "Storage", "medium", [], [], ["ERR-SYS-002"], "KB-0008", "frustrated_user"),
    t("photos from company event gone", "the marketing team photos from last weeks company event that were on the shared drive are all gone. someone deleted them or the folder was moved. we need these for the newsletter going out friday", "Storage", "high", ["prod-nfs-01"], ["nfs"], [], None, "frustrated_user"),

    # ── L2 ENGINEER (34 tickets) ──
    # Infrastructure (6)
    t("containerd runtime socket error on prod-k8s-node-01", "kubelet on prod-k8s-node-01 reporting: 'failed to create containerd task: OCI runtime create failed: runc did not terminate successfully: context deadline exceeded'. Happening for all new pod schedulings since 14:30 UTC. Existing pods running fine. containerd service logs show socket timeout on /run/containerd/containerd.sock. Suspect containerd process hung.", "Infrastructure", "critical", ["prod-k8s-node-01"], ["kubernetes"], [], None, "l2_engineer",
     steps=["Restarted containerd: systemctl restart containerd", "Verified kubelet reconnected to containerd socket", "New pods scheduling successfully", "Added containerd health check to monitoring"]),
    t("systemd-resolved consuming 4GB RAM on prod-web-01", "ps_mem.py shows systemd-resolved at 4.1GB RSS on prod-web-01. Normal is ~50MB. DNS resolution working but extremely slow (2-3s per query). NGINX health checks timing out due to slow DNS. journalctl -u systemd-resolved shows millions of NXDOMAIN responses cached — suspect DNS amplification from misconfigured app.", "Infrastructure", "high", ["prod-web-01"], ["nginx"], ["ERR-DNS-001"], None, "l2_engineer"),
    t("cgroup memory limit causing OOM on prod-app-02 containers", "Docker containers on prod-app-02 hitting cgroup memory limits. docker stats shows order-service at 1.97GB/2GB limit. Host has 16GB free but container cgroup prevents usage. dmesg: 'memory cgroup out of memory: Killed process 8847 (java)'. Need to increase container memory limit or optimize JVM.", "Infrastructure", "high", ["prod-app-02"], ["order-service"], ["ERR-K8S-001"], "KB-0004", "l2_engineer"),
    t("NTP drift detected — prod-db-01 clock skew 4.7 seconds", "ntpstat on prod-db-01 shows unsynchronised, time offset 4700ms. PostgreSQL replication complaining about timestamp inconsistencies. chronyd service failed after recent kernel update. TLS certificate validation also failing due to clock skew. Need to resync NTP immediately.", "Infrastructure", "high", ["prod-db-01"], ["postgresql"], [], None, "l2_engineer"),
    t("Ansible playbook timeout deploying to prod-k8s-node-02", "ansible-playbook site.yml failing on prod-k8s-node-02 with: 'Timeout waiting for privilege escalation prompt'. SSH works manually. Suspect PAM module delay — pam_systemd taking 90s+ to create session. /var/log/auth.log shows: 'pam_systemd: Failed to create session: Connection timed out'.", "Infrastructure", "medium", ["prod-k8s-node-02"], ["kubernetes"], [], None, "l2_engineer"),
    t("journald consuming 8GB disk on prod-mon-01", "journalctl --disk-usage shows 8.2GB on prod-mon-01. SystemMaxUse not set (default unlimited). Prometheus exporter logging at DEBUG level since CHG-9995 — generating 500MB/day of journal entries. /var at 92%.", "Infrastructure", "medium", ["prod-mon-01"], ["prometheus"], ["ERR-SYS-002"], "KB-0008", "l2_engineer"),

    # Application (6)
    t("OrderService gRPC deadline exceeded on internal service calls", "OrderService on prod-app-01 gRPC calls to InventoryService failing with DEADLINE_EXCEEDED. Default deadline 5s, actual p99 latency 12s. InventoryService logs show slow PostgreSQL queries (no index on product_id+warehouse_id). 30% of checkout requests failing.", "Application", "critical", ["prod-app-01"], ["order-service", "postgresql"], [], None, "l2_engineer", secondary="Database"),
    t("React frontend build failing — node_modules corruption", "CI/CD pipeline failing on frontend build: 'Module not found: react-dom'. npm ci succeeds but node_modules/.cache corrupted. Suspect Docker layer caching serving stale node_modules. Only affects builds from prod-k8s-node-01 runner.", "Application", "medium", ["prod-k8s-node-01"], ["kubernetes"], [], None, "l2_engineer"),
    t("AuthService rate limiter blocking legitimate traffic", "AuthService rate limiter on prod-app-03 blocking login attempts at 10 req/s per IP. Corporate NAT means all 500 office users share one IP. During morning login spike (08:30-09:00), 40% of employees getting 429 Too Many Requests.", "Application", "high", ["prod-app-03"], ["auth-service"], [], None, "l2_engineer"),
    t("WebSocket connections dropping after 60 seconds", "Real-time notification WebSocket connections on prod-web-01 dropping exactly at 60s. NGINX proxy_read_timeout default is 60s. Notifications stop working until page refresh. Affects 2,000 active users.", "Application", "high", ["prod-web-01"], ["nginx"], [], "KB-0002", "l2_engineer"),
    t("Spring Boot actuator endpoints exposed to public internet", "Discovered /actuator/env and /actuator/heapdump accessible without auth on prod-app-01:8080. Contains database credentials and JVM heap data. Security scanner flagged as critical. Need to restrict actuator to management port or add auth.", "Application", "critical", ["prod-app-01"], ["order-service"], ["ERR-SEC-001"], None, "l2_engineer", secondary="Security"),
    t("API response payload size exceeding 10MB causing OOM in mobile app", "OrderService /api/orders endpoint returning 12MB JSON payload for customers with >1000 orders. Mobile app OOM on parsing. API has no pagination — returns all orders in single response. Need server-side pagination with limit/offset.", "Application", "high", ["prod-app-01"], ["order-service", "api-gateway"], [], None, "l2_engineer"),

    # Database (6)
    t("PostgreSQL streaming replication WAL sender disconnecting", "pg_stat_replication on prod-db-01 shows replica prod-db-02 state='streaming' then suddenly disconnects every 15 minutes. Replica falls behind, catches up, disconnects again. wal_sender_timeout=60s, wal_keep_size=1GB. Network between servers stable. Suspect wal_sender process killed by OOM.", "Database", "high", ["prod-db-01", "prod-db-02"], ["postgresql"], [], None, "l2_engineer"),
    t("PostgreSQL bloat — orders table 40GB actual data in 120GB table", "pgstattuple('orders') on prod-db-01: table_len=120GB, tuple_len=40GB, dead_tuple_len=75GB. Bloat ratio: 63%. autovacuum_vacuum_scale_factor=0.2 but table too large for default settings. Queries scanning dead tuples causing 3x slowdown.", "Database", "high", ["prod-db-01"], ["postgresql"], [], None, "l2_engineer",
     steps=["Set autovacuum_vacuum_scale_factor=0.01 for orders table", "Ran manual VACUUM FULL orders (required maintenance window)", "Table reduced from 120GB to 42GB", "Query performance improved 3x"]),
    t("Redis Sentinel failover loop — master flapping", "Redis Sentinel on prod-app-01 triggering failover every 5 minutes. Sentinel log: '+sdown master mymaster 10.0.2.10 6379' then '-sdown master mymaster' 30s later. Root cause: network microbursts causing 2-3s connectivity drops. down-after-milliseconds=1000 too aggressive.", "Database", "critical", ["prod-app-01"], ["redis"], [], "KB-0007", "l2_engineer"),
    t("PostgreSQL pg_hba.conf rejecting connections from new subnet", "After network restructuring, prod-app-03 (new IP 10.0.2.15) cannot connect to prod-db-01 PostgreSQL. pg_hba.conf only allows 10.0.2.0/28 (old range). New subnet is 10.0.2.0/24. Need to update pg_hba.conf and reload.", "Database", "high", ["prod-db-01", "prod-app-03"], ["postgresql"], ["ERR-PG-002"], None, "l2_engineer"),
    t("Connection leak detected — idle connections growing linearly", "prod-db-01 idle connections: 87 at 08:00, 145 at 12:00, 203 at 16:00. Growing ~30/hour. pg_stat_activity shows connections from prod-app-01 with query='SET application_name' in idle state for hours. HikariCP leak detection disabled. Will hit max_connections=300 by midnight.", "Database", "high", ["prod-db-01", "prod-app-01"], ["postgresql"], ["ERR-PG-001"], "KB-0001", "l2_engineer"),
    t("pg_dump backup taking 6 hours instead of usual 45 minutes", "Nightly pg_dump on prod-db-01 started at 02:00, still running at 08:00. Normal duration: 45 min. du -sh shows dump file at 38GB (expected 45GB). iostat shows competing I/O from autovacuum running on large tables. Need to schedule backup window without autovacuum.", "Database", "medium", ["prod-db-01"], ["postgresql"], [], None, "l2_engineer"),

    # Network (4)
    t("MTU mismatch causing packet fragmentation between DCs", "tcpdump on sw-core-01 showing IP fragmentation for packets >1400 bytes between ap-south-1 and ap-south-2. VPN tunnel MTU=1500 but underlying link MTU=1422 after ISP change. PMTUD being blocked by intermediate firewall. Causing TCP performance degradation for large transfers.", "Network", "high", [], [], [], None, "l2_engineer"),
    t("ARP storm on VLAN 200 — switch CPU 99%", "sw-core-01 show processes cpu shows 99%. show mac address-table shows 45,000 entries on VLAN 200. ARP inspection log: 2000 ARP packets/sec from MAC 00:1A:2B:3C:4D:5E. Traced to misconfigured Docker bridge on prod-k8s-node-01 broadcasting ARP for non-existent IPs.", "Network", "critical", [], ["kubernetes"], [], None, "l2_engineer"),
    t("ACL blocking ICMP — monitoring false positives", "Prometheus blackbox exporter showing prod-app-02 as down. ping fails but ssh works. New ACL applied to fw-prod-01 (CHG-9999) blocks ICMP. All ICMP-based monitoring broken. Need to allow ICMP type 8 (echo request) in ACL.", "Network", "medium", ["prod-app-02"], ["prometheus"], ["ERR-FW-001"], "KB-0010", "l2_engineer"),
    t("DNS round-robin not distributing evenly", "dig prod-web.internal shows both prod-web-01 and prod-web-02 IPs but 90% of connections hitting prod-web-01. DNS TTL=300s and clients caching first response. Need to switch from DNS round-robin to load balancer health-checked distribution.", "Network", "medium", ["prod-web-01", "prod-web-02"], ["nginx"], [], None, "l2_engineer"),

    # Security (4)
    t("Log4Shell scan results — 3 vulnerable services identified", "Dependency scan found log4j-core 2.14.0 in OrderService, AuthService, and ReportService. CVE-2021-44228 (CVSS 10.0). All three services deployed on production. WAF rule in place as temporary mitigation but need library upgrade to 2.17.1.", "Security", "critical", ["prod-app-01", "prod-app-03"], ["order-service", "auth-service"], [], None, "l2_engineer"),
    t("JWT secret key shared across all environments", "Code review found JWT_SECRET env var identical in dev, staging, and production. Any dev environment JWT is valid in production. Tokens signed in dev can access production APIs. Need unique secrets per environment and token invalidation.", "Security", "critical", [], ["auth-service", "api-gateway"], ["ERR-SEC-001"], None, "l2_engineer"),
    t("Unencrypted PII in application debug logs", "Production debug logs on prod-app-01 contain unencrypted customer email addresses and phone numbers. Log rotation keeps 30 days. GDPR violation risk. Debug logging was enabled for troubleshooting 2 weeks ago and never turned off. LOG_LEVEL still set to DEBUG.", "Security", "high", ["prod-app-01"], ["order-service"], [], None, "l2_engineer"),
    t("SSH host key changed warning on prod-db-02", "All SSH connections to prod-db-02 showing 'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED'. Automation scripts failing with StrictHostKeyChecking=yes. No authorized maintenance or rebuild occurred. Could indicate MITM or unauthorized server rebuild. Need investigation.", "Security", "critical", ["prod-db-02"], [], ["ERR-SEC-001"], None, "l2_engineer"),

    # Storage (4)
    t("Thin-provisioned LUN overcommitted — 150% allocation", "SAN management showing thin LUN allocated to prod-db-01 at 150% overcommitment. Physical storage pool at 88%. If multiple LUNs grow simultaneously, pool exhaustion will cause I/O errors across all LUNs. Need to add physical capacity or reduce allocation.", "Storage", "critical", ["prod-db-01"], ["postgresql"], [], None, "l2_engineer"),
    t("NFS write performance degraded 10x after kernel update", "NFS write throughput on prod-nfs-01 dropped from 500MB/s to 50MB/s after kernel update to 5.15.0-97. nfsstat shows high retransmissions. Suspect NFS delegation issues with new kernel. Read performance unaffected.", "Storage", "high", ["prod-nfs-01"], ["nfs"], [], "KB-0006", "l2_engineer"),
    t("Backup deduplication ratio dropped from 5:1 to 1.2:1", "Backup storage consumption spiked 4x this week. Deduplication engine showing 1.2:1 ratio instead of normal 5:1. Traced to new encrypted backup feature — encrypted data doesn't deduplicate. 2TB additional storage consumed in 5 days.", "Storage", "high", ["prod-nfs-01"], [], [], None, "l2_engineer"),
    t("LVM snapshot consuming more space than original volume", "LVM snapshot of data volume on prod-db-02 at 95% full. Original volume has high write rate during business hours causing snapshot COW overhead. If snapshot fills to 100%, it becomes invalid and is auto-removed. Need to either merge or remove snapshot.", "Storage", "high", ["prod-db-02"], ["postgresql"], [], None, "l2_engineer"),

    # ── MANAGER (33 tickets) ──
    # Infrastructure (5)
    t("End-of-life Windows Server 2012 — compliance risk", "Security audit flagged that prod-ldap-01 is running Windows Server 2022 but two other systems still on Server 2012 R2 (end of extended support). No security patches available. Compliance team requiring migration plan within 30 days.", "Infrastructure", "high", ["prod-ldap-01"], ["active-directory"], [], None, "manager"),
    t("Capacity planning request for Q3 product launch", "Product team is planning a major feature launch in Q3 expected to double our user base. Current infrastructure handles 10,000 concurrent users. Need capacity assessment and scaling plan for 20,000 concurrent users. Budget approval needed by May 30.", "Infrastructure", "medium", ["prod-app-01", "prod-web-01", "prod-db-01"], ["order-service", "nginx", "postgresql"], [], None, "manager"),
    t("SLA report showing 99.2% uptime — below 99.9% target", "Monthly SLA report shows 99.2% uptime instead of our committed 99.9%. Three incidents contributed to 6.3 hours downtime. Client account managers requesting root cause for each incident. Need post-incident review completed by Friday.", "Infrastructure", "high", [], [], [], None, "manager"),
    t("Green IT initiative — reduce datacenter power consumption 20%", "Board approved green IT initiative to reduce datacenter power consumption by 20% by year end. Need assessment of current power usage, rightsizing opportunities, and migration candidates for cloud. Initial proposal due in 2 weeks.", "Infrastructure", "low", [], [], [], None, "manager"),
    t("IT budget variance — infrastructure costs 30% over plan", "Finance flagged Q1 infrastructure costs 30% over budget. Main drivers: unplanned storage expansion and cloud egress charges. Need cost optimization recommendations and revised Q2-Q4 forecast.", "Infrastructure", "medium", [], [], [], None, "manager"),

    # Application (5)
    t("Customer portal redesign launch delayed — critical bugs found in UAT", "The customer portal redesign launch scheduled for May 1 has critical bugs found in UAT. Payment processing and order history features failing. Business stakeholders need an updated timeline. Marketing has already announced the launch date.", "Application", "critical", ["prod-app-01", "prod-web-01"], ["order-service", "nginx"], [], None, "manager"),
    t("Third-party API provider deprecating v1 — migration deadline June 30", "Our payment provider notified that API v1 (which we currently use) will be deprecated June 30. Migration to v3 requires significant code changes. Engineering team needs to prioritize this. Impact: all payment processing will break if not migrated.", "Application", "high", ["prod-app-01"], ["order-service"], [], None, "manager"),
    t("Mobile app store rating dropped to 3.2 — stability issues", "Our mobile app rating on Google Play dropped from 4.5 to 3.2 in the last 2 weeks. Reviews mention frequent crashes and slow loading. This is affecting new user acquisition. Product and engineering need to prioritize stability fixes.", "Application", "high", [], ["api-gateway", "order-service"], [], None, "manager"),
    t("Accessibility audit failed — WCAG 2.1 compliance required by law", "External accessibility audit found 47 WCAG 2.1 violations on our customer portal. Legal team says we must comply within 90 days to avoid potential lawsuits. Need engineering team assessment of effort required.", "Application", "high", ["prod-web-01"], ["nginx"], [], None, "manager"),
    t("API documentation out of date — partner integration failing", "Two integration partners reported issues this week because our API documentation doesn't match actual behavior. Version mismatch between docs and production. Developer relations team requesting documentation update as priority.", "Application", "medium", [], ["api-gateway", "order-service"], [], None, "manager"),

    # Database (5)
    t("Database cost optimization — Oracle to PostgreSQL migration assessment", "License renewal for Oracle database is $450K/year. CTO wants assessment of migrating to PostgreSQL to reduce costs. Need feasibility study covering: data migration, application compatibility, performance comparison, and timeline.", "Database", "medium", ["prod-db-01"], ["postgresql"], [], None, "manager"),
    t("GDPR data deletion request backlog — 200 pending requests", "Privacy team reports 200 pending data deletion requests from customers, oldest is 45 days. GDPR requires completion within 30 days. Current manual process takes 2 hours per request. Need automated solution urgently.", "Database", "critical", ["prod-db-01"], ["postgresql"], [], None, "manager"),
    t("Read replica performance inconsistent — analytics team complaining", "Analytics team reports that their queries on the read replica take anywhere from 2 seconds to 5 minutes for the same report. Inconsistent performance making it impossible to deliver timely insights. Suspect replication lag or shared resource contention.", "Database", "high", ["prod-db-02"], ["postgresql"], [], None, "manager"),
    t("Database audit trail missing for regulatory requirement", "Compliance team discovered that our database doesn't have a complete audit trail of data modifications. Regulators require full audit history for financial transactions. Need to implement database-level audit logging.", "Database", "high", ["prod-db-01"], ["postgresql"], [], None, "manager"),
    t("Reporting database refresh taking too long — blocking morning standup", "The overnight reporting database refresh is supposed to complete by 6 AM but regularly finishes at 9:30 AM. The operations team can't run their morning reports for the standup meeting. Need optimization or architecture change.", "Database", "medium", ["prod-db-02"], ["postgresql"], [], None, "manager"),

    # Network (5)
    t("WiFi coverage gaps in new building wing — 40 employees affected", "The new east wing (floors 3-5) has poor WiFi coverage. Signal drops and slow speeds reported by 40 employees. Site survey was done 6 months ago but furniture layout changed. Need updated survey and additional access points.", "Network", "medium", [], [], [], None, "manager"),
    t("DDoS protection needed — competitor experienced attack last week", "A competitor in our space experienced a major DDoS attack last week that took them offline for 12 hours. Our current setup has no DDoS mitigation. CISO requesting evaluation of DDoS protection solutions with recommendation by next week.", "Network", "high", [], ["nginx", "api-gateway"], [], None, "manager"),
    t("Cross-region latency affecting collaboration between offices", "Mumbai and Hyderabad teams report significant lag when collaborating on shared documents and video calls. Network team says 120ms latency is normal for cross-region. Business impact: teams avoiding real-time collaboration. Need evaluation of optimization options.", "Network", "medium", [], [], [], None, "manager"),
    t("Vendor VPN tunnel for partner integration — setup needed by May 15", "Business development signed a new partnership requiring dedicated VPN tunnel to partner's network. Technical requirements received today. Integration go-live date is May 15. Network team please assess and plan.", "Network", "high", [], [], [], "KB-0003", "manager"),
    t("Network segmentation audit for PCI compliance", "PCI auditor requires evidence of network segmentation between cardholder data environment and general corporate network. Current flat network doesn't meet requirements. Need segmentation plan and implementation timeline.", "Network", "critical", [], [], [], "KB-0010", "manager"),

    # Security (6)
    t("Cyber insurance renewal — need updated security posture assessment", "Cyber insurance renewal is due June 1. Insurer requires updated security assessment including: patching cadence, MFA coverage, backup testing results, incident response plan. CISO needs all teams to provide their sections by May 15.", "Security", "medium", [], [], [], None, "manager"),
    t("Third-party vendor access not revoked after contract ended", "Procurement flagged that 3 vendor accounts still have VPN and system access despite contracts ending in Q4 2025. This is a security and compliance violation. Need immediate access revocation and process fix.", "Security", "critical", ["prod-ldap-01"], ["active-directory"], [], "KB-0009", "manager"),
    t("Shadow IT discovery — 15 unauthorized SaaS tools in use", "IT governance review found 15 unauthorized SaaS tools being used across departments, with company data in tools that haven't been security reviewed. Examples: unauthorized file sharing, project management, and communication tools. Need policy enforcement and approved alternatives.", "Security", "high", [], [], [], None, "manager"),
    t("Incident response plan needs updating — last review 2 years ago", "Our incident response plan was last updated in 2024. It doesn't cover current infrastructure, team structure has changed, and contact information is outdated. Regulators may ask for current plan during next audit.", "Security", "medium", [], [], [], None, "manager"),
    t("Customer reporting data breach via support channel", "A customer contacted support claiming they can see another customer's account details when logged in. Support team verified the issue — appears to be a session handling bug. This is a potential data breach requiring notification under GDPR. Legal and security teams need to be engaged immediately.", "Security", "critical", ["prod-app-01"], ["auth-service", "order-service"], ["ERR-SEC-001"], None, "manager", secondary="Application"),
    t("Annual security awareness training overdue — compliance deadline passed", "HR reports that 40% of employees have not completed their mandatory annual security awareness training. Compliance deadline was March 31. Need to push remaining employees to complete training within 2 weeks.", "Security", "medium", [], [], [], None, "manager"),

    # Storage (5)
    t("Cloud storage migration ROI analysis requested", "CFO wants ROI analysis for migrating on-premise NFS storage to AWS S3/EFS. Current on-prem storage: 50TB, growing 500GB/month. Need cost comparison, performance implications, and migration approach.", "Storage", "medium", ["prod-nfs-01"], ["nfs"], [], None, "manager"),
    t("Data classification project needed for storage tiering", "Storage costs are growing 15% quarterly. CTO wants hot/warm/cold data classification to move infrequently accessed data to cheaper storage. Need assessment of data access patterns and tiering strategy.", "Storage", "medium", ["prod-nfs-01", "prod-db-01"], ["nfs", "postgresql"], [], None, "manager"),
    t("Ransomware protection for backup infrastructure", "After seeing recent ransomware attacks in the industry, the CISO wants immutable backups implemented. Current backups on prod-nfs-01 can be modified or deleted. Need air-gapped or immutable backup solution.", "Storage", "high", ["prod-nfs-01"], ["nfs"], [], None, "manager", secondary="Security"),
    t("Storage performance metrics needed for SLA reporting", "Operations team needs monthly storage performance metrics (IOPS, latency, throughput) for client SLA reporting. Currently collected manually. Need automated reporting solution integrated with Grafana dashboards.", "Storage", "low", ["prod-nfs-01"], ["nfs", "grafana"], [], None, "manager"),
    t("End-of-life NAS appliance replacement needed", "The NAS appliance supporting prod-nfs-01 reaches end-of-life in August. Vendor will stop providing firmware updates. Need replacement evaluation: buy new appliance vs migrate to software-defined storage vs cloud.", "Storage", "high", ["prod-nfs-01"], ["nfs"], [], None, "manager"),
]


def main():
    existing = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)

    combined = existing + tickets

    with open(OUTPUT_FILE, "w") as f:
        json.dump(combined, f, indent=2)

    from collections import Counter
    cats = Counter(t["category"] for t in combined)
    personas = Counter(t["persona"] for t in combined)
    print(f"Existing: {len(existing)}")
    print(f"New: {len(tickets)}")
    print(f"Total: {len(combined)}")
    print(f"\nCategories: {dict(sorted(cats.items()))}")
    print(f"Personas: {dict(sorted(personas.items()))}")


if __name__ == "__main__":
    main()
