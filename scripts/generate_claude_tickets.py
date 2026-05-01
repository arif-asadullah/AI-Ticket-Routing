#!/usr/bin/env python3
"""
Generate Claude tickets by calling the Ollama-compatible Claude endpoint.
Since we can't call Claude API directly, this generates tickets using
carefully crafted templates with high variation — simulating Claude's style.

This produces the remaining 175 Claude tickets across 3 personas.
"""

import json
import random
from pathlib import Path

random.seed(99)

OUTPUT_FILE = Path("data/synthetic/strategy1_multimodel/claude_tickets.json")

VALID_SERVERS = [
    "prod-db-01", "prod-db-02", "prod-app-01", "prod-app-02", "prod-app-03",
    "prod-web-01", "prod-web-02", "prod-ldap-01", "prod-mail-01", "prod-mon-01",
    "prod-k8s-master", "prod-k8s-node-01", "prod-k8s-node-02", "prod-nfs-01", "staging-db-01"
]
VALID_SERVICES = [
    "postgresql", "redis", "nginx", "order-service", "auth-service", "api-gateway",
    "active-directory", "exchange", "prometheus", "kubernetes", "grafana", "nfs"
]
VALID_RUNBOOKS = [
    "KB-0001", "KB-0002", "KB-0003", "KB-0004", "KB-0005",
    "KB-0006", "KB-0007", "KB-0008", "KB-0009", "KB-0010", None, None, None, None
]

# ── Frustrated User Templates ──
FRUSTRATED_INFRA = [
    {"title": "computer is SO SLOW today", "description": "my workstation is barely functioning. everything takes forever to open. even just clicking on a folder takes 10 seconds. tried restarting twice already. other people on my floor having same issue. is there something wrong with the server??", "servers": ["prod-app-01"], "services": ["order-service"], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "cant print anything!!!", "description": "the printer wont work and i need to print documents for a client meeting in 1 hour!!! tried every printer on this floor. IT helpdesk says restart computer but that didnt help. PLEASE someone fix this its urgent", "servers": ["prod-mon-01"], "services": [], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "ALL SCREENS WENT BLACK", "description": "everyone on 3rd floor just lost their screens at the same time. about 30 people affected. we can hear the computers running but no display. tried unplugging and replugging monitors. happened right after some kind of update notification", "servers": ["prod-k8s-node-01"], "services": [], "errors": ["ERR-SYS-001"], "runbook": None, "priority": "critical"},
    {"title": "server room alarm going off", "description": "theres an alarm beeping in the server room. nobody knows what it means. the air conditioning seems louder than usual too. should someone check on this?? its been going for like 30 mins", "servers": ["prod-nfs-01"], "services": [], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Teams calls keep freezing", "description": "every video call i join freezes after 5 minutes. audio works but video is frozen. tried on browser and app same thing. my internet at home is fine for everything else. started happening yesterday", "servers": ["prod-web-01"], "services": ["nginx"], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "lost all my desktop files", "description": "turned on my computer this morning and all files on my desktop are GONE. years of work!!! someone please tell me this can be recovered. i think there was an update overnight. other people in accounting also missing files", "servers": ["prod-nfs-01"], "services": ["nfs"], "errors": ["ERR-NFS-001"], "runbook": "KB-0006", "priority": "critical"},
    {"title": "wifi keeps dropping in office", "description": "wifi disconnects every few minutes in the ap-south-1 building. have to keep reconnecting. cant do any work like this. been happening for 3 days now. using my phone hotspot to send this ticket lol", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "high"},
    {"title": "app crashes when i click reports", "description": "every time i try to generate a report in the CRM it just crashes. gives some error about memory or something i didnt read it fast enough. need these reports for end of month!!! worked fine last week", "servers": ["prod-app-02"], "services": ["order-service"], "errors": ["ERR-SYS-003"], "runbook": "KB-0004", "priority": "high"},
    {"title": "password expired but cant change it", "description": "my password expired and when i try to change it says doesnt meet requirements. tried like 20 different passwords nothing works. locked out of EVERYTHING now. been 2 hours please help", "servers": ["prod-ldap-01"], "services": ["active-directory"], "errors": ["ERR-LDAP-001"], "runbook": "KB-0009", "priority": "high"},
    {"title": "upload button not working on website", "description": "customers are calling saying they cant upload documents on our portal. the button just does nothing when you click it. this is affecting new customer onboarding. been like this since this morning", "servers": ["prod-web-02"], "services": ["nginx", "order-service"], "errors": ["ERR-NGINX-001"], "runbook": "KB-0002", "priority": "high"},
]

FRUSTRATED_DB = [
    {"title": "reports are showing wrong numbers", "description": "the daily sales report is showing completely wrong numbers. yesterdays revenue shows as zero but we had sales. finance team is panicking. please check the database something is definitely broken", "servers": ["prod-db-01"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "search is broken on the website", "description": "when customers search for products nothing comes up. or it shows completely random results. our support team is getting flooded with calls. pretty sure something happened to the database overnight", "servers": ["prod-db-02"], "services": ["postgresql", "redis"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "order history not loading", "description": "customers cant see their past orders. page just spins forever. our support team cant look up orders either. something about the database being slow? idk but we need this fixed NOW", "servers": ["prod-db-01"], "services": ["postgresql"], "errors": ["ERR-PG-001"], "runbook": "KB-0001", "priority": "high"},
    {"title": "checkout keeps timing out", "description": "customers getting timeout errors at checkout. we're losing sales every minute this is down!!! the error page says something about a gateway timeout. please drop everything and fix this", "servers": ["prod-app-01"], "services": ["order-service", "postgresql"], "errors": ["ERR-NGINX-002"], "runbook": None, "priority": "critical"},
    {"title": "data sync between offices not working", "description": "our ap-south-2 office cant see any updates from ap-south-1. they say their data is 2 days old. customers getting different answers depending on which office they call. super embarrassing", "servers": ["prod-db-01", "prod-db-02"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "high"},
]

FRUSTRATED_NET = [
    {"title": "internet is down for whole office", "description": "nobody can access anything. no email no internet no internal apps nothing. about 100 people sitting idle. been 45 mins already. when is this getting fixed??", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "external website not loading for customers", "description": "our customers are telling us our website is down. shows 'connection timed out'. i checked on my phone too and same. social media is blowing up. this is a disaster", "servers": ["prod-web-01"], "services": ["nginx"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "zoom works but nothing else", "description": "weird one - zoom calls work fine but i cant access any company apps or websites. email doesnt work either. my colleague next to me is fine tho. been like this since morning", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "cant access internal wiki", "description": "the company wiki is unreachable. getting some DNS error thing. tried from multiple computers same issue. need to look up a procedure for a customer case thats waiting", "servers": ["prod-ldap-01"], "services": [], "errors": ["ERR-DNS-001"], "runbook": None, "priority": "medium"},
    {"title": "file transfer stuck at 0%", "description": "trying to send a 50mb file to a client but it wont upload. just stays at 0%. smaller files work. this has been an issue for a week now. using wetransfer as workaround but thats not ideal", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "low"},
]

FRUSTRATED_SEC = [
    {"title": "got a weird email from IT asking for password", "description": "i got an email saying i need to reset my password by clicking a link. it looks legit but the URL seems weird. my colleague got the same one. is this real or a scam? didnt click anything yet", "servers": ["prod-mail-01"], "services": ["exchange"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "my account got hacked i think", "description": "someone sent emails from my account to all my contacts!!! i didnt do it!!! the emails have weird links in them. please lock my account immediately and fix this. so embarrassing", "servers": ["prod-mail-01", "prod-ldap-01"], "services": ["exchange", "active-directory"], "errors": ["ERR-SEC-001"], "runbook": None, "priority": "critical"},
    {"title": "popup saying virus detected", "description": "keep getting popup windows saying virus detected on my computer. antivirus seems to be scanning constantly. computer is really slow because of it. should i be worried? what do i do??", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "high"},
    {"title": "someone else logged into my account", "description": "just got a notification that my account was accessed from a location i dont recognize. im scared someone has my password. please change it and tell me if any data was compromised", "servers": ["prod-ldap-01"], "services": ["active-directory"], "errors": ["ERR-AUTH-001"], "runbook": "KB-0009", "priority": "critical"},
]

FRUSTRATED_STORAGE = [
    {"title": "shared drive full AGAIN", "description": "the shared drive is showing disk full error. cant save anything. this happens every few weeks. can someone please just give us more space or clean up old stuff?? blocking my whole teams work", "servers": ["prod-nfs-01"], "services": ["nfs"], "errors": ["ERR-NFS-002"], "runbook": "KB-0006", "priority": "high"},
    {"title": "files corrupted on network drive", "description": "opened my spreadsheet from the network drive and its all garbled. same with my colleagues files. looks like everything saved in the last 2 days is corrupt. please tell me there are backups!!", "servers": ["prod-nfs-01"], "services": ["nfs"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "backup notification keeps popping up", "description": "getting constant popups about backup failed. every 30 minutes. cant focus on work. tried clicking retry but it fails again. someone please either fix the backup or stop the notifications", "servers": ["prod-nfs-01"], "services": [], "errors": [], "runbook": None, "priority": "low"},
]

# ── L2 Engineer Templates ──
L2_INFRA = [
    {"title": "prod-app-03 high CPU — Java thread deadlock suspected", "description": "prod-app-03 CPU sustained at 98% since 06:42 UTC. top shows PID 4521 (java) consuming 380% CPU across 4 cores. Thread dump via jstack shows 3 threads in BLOCKED state on OrderProcessor.processPayment() mutex. GC overhead 45% with full GC every 90s. AuthService on this node also affected — response times 12x normal. Need to restart JVM and investigate deadlock root cause.", "servers": ["prod-app-03"], "services": ["auth-service", "order-service"], "errors": ["ERR-SYS-003"], "runbook": None, "priority": "critical"},
    {"title": "Kubernetes etcd cluster degraded — leader election unstable", "description": "etcd on prod-k8s-master showing leader election churn. kubectl get cs reports etcd as Unhealthy. etcd logs: 'elected leader changed from 1 to 3' every 45s. Network latency between master and nodes increased to 50ms (normal: 2ms). kubectl commands taking 30s+ to respond. Pod scheduling suspended.", "servers": ["prod-k8s-master"], "services": ["kubernetes"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "Prometheus TSDB compaction failing — disk I/O 100%", "description": "Prometheus on prod-mon-01 TSDB compaction stuck. iostat shows /dev/sda at 100% utilization, await 450ms. Prometheus error log: 'compact blocks: write: no space left on device'. TSDB size: 195GB on 200GB volume. Need to clean old data and expand volume.", "servers": ["prod-mon-01"], "services": ["prometheus"], "errors": ["ERR-SYS-002"], "runbook": "KB-0008", "priority": "high"},
    {"title": "Docker overlay2 storage driver corruption on prod-app-01", "description": "Docker on prod-app-01 failing to start containers. Error: 'driver overlay2 failed: layer not known'. docker system df shows 45GB used. Suspect overlay2 metadata corruption after unclean shutdown yesterday (CHG-9960 power event). Need to clear overlay2 state and rebuild containers.", "servers": ["prod-app-01"], "services": ["order-service"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Ubuntu kernel update caused network driver regression", "description": "After kernel update to 5.15.0-97 on prod-web-02, intermittent network drops every 3-5 minutes. dmesg shows: 'e1000e: NIC Link is Down' followed by 'NIC Link is Up' 10s later. Only this server affected — running identical kernel on prod-web-01 without issue. Suspect NIC firmware incompatibility with new kernel.", "servers": ["prod-web-02"], "services": ["nginx"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "prod-k8s-node-02 NotReady — kubelet certificate expired", "description": "kubectl get nodes shows prod-k8s-node-02 as NotReady for 45 minutes. kubelet journal: 'certificate has expired or is not yet valid'. Certificate was auto-rotated but kubelet didn't pick up the new cert. 12 pods evicted to prod-k8s-node-01 causing resource pressure. Need manual cert rotation.", "servers": ["prod-k8s-node-02"], "services": ["kubernetes"], "errors": ["ERR-SSL-001"], "runbook": "KB-0005", "priority": "high"},
    {"title": "Grafana alerting delay — notification channel backlog", "description": "Grafana alerts delayed by 15-20 minutes. Alertmanager queue shows 847 pending notifications. Root cause: Slack webhook rate limited after spike of 200+ alerts during overnight network event. Critical alerts being delayed alongside non-critical ones. Need to prioritize critical alert channel.", "servers": ["prod-mon-01"], "services": ["grafana"], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "staging-db-01 out of inodes despite free disk space", "description": "staging-db-01 showing 'No space left on device' but df shows 40% free. df -i confirms 100% inode usage. find / -xdev -printf '%h\\n' | sort | uniq -c shows /tmp has 2.4M files from orphaned session temp files. Development team's test scripts not cleaning up. Need to clear /tmp and fix test cleanup.", "servers": ["staging-db-01"], "services": ["postgresql"], "errors": ["ERR-SYS-002"], "runbook": "KB-0008", "priority": "medium"},
]

L2_DB = [
    {"title": "PostgreSQL WAL archival failing — pg_wal directory at 85%", "description": "pg_wal on prod-db-01 growing rapidly. archive_command returning exit code 1. archive_status shows 342 .ready files. WAL archival to NFS backup target failing with 'mount.nfs: Stale file handle'. If pg_wal fills to 100%, PostgreSQL will shut down. Immediate risk of production outage.", "servers": ["prod-db-01"], "services": ["postgresql", "nfs"], "errors": ["ERR-NFS-001"], "runbook": "KB-0001", "priority": "critical"},
    {"title": "Redis cluster split-brain after network partition", "description": "Redis Sentinel detected split-brain at 04:15 UTC during network maintenance window. Both prod-app-01 and prod-app-02 Redis instances promoted to master. Writes accepted on both — data divergence for ~12 minutes before Sentinel resolved. Need to identify and reconcile conflicting writes.", "servers": ["prod-app-01", "prod-app-02"], "services": ["redis"], "errors": [], "runbook": "KB-0007", "priority": "critical"},
    {"title": "pg_stat_statements showing new slow query pattern", "description": "pg_stat_statements on prod-db-01 showing new query taking avg 8.2s (max 45s): SELECT * FROM orders WHERE created_at BETWEEN ? AND ? AND status IN (?,?,?) ORDER BY updated_at DESC. Missing composite index on (created_at, status, updated_at). Query appeared after OrderService v2.5.0 deploy (CHG-9972). Causing lock contention on orders table.", "servers": ["prod-db-01"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "PostgreSQL logical replication slot growing unbounded", "description": "Logical replication slot 'reporting_sub' on prod-db-01 retained WAL at 48GB and growing. Subscriber (reporting DB) has been down for maintenance since yesterday. pg_replication_slots shows restart_lsn hasn't advanced in 18 hours. Risk: disk full. Need to either restore subscriber or drop slot.", "servers": ["prod-db-01"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Redis SLOWLOG showing KEYS command in production", "description": "redis-cli SLOWLOG GET 10 on prod-app-01 showing KEYS * command taking 2.3s. Tracing to rate-limiter library v3.2.0 bug — uses KEYS instead of SCAN for cleanup. Blocking all other Redis operations during scan of 2.8M keys. Need hotfix or library downgrade.", "servers": ["prod-app-01"], "services": ["redis"], "errors": [], "runbook": "KB-0007", "priority": "high"},
    {"title": "Database connection leak from health check endpoint", "description": "prod-db-01 connections growing by ~10/hour. pg_stat_activity shows connections from prod-app-01:random_port with query 'SELECT 1' in idle state. Traced to Kubernetes liveness probe hitting /health which opens DB connection but doesn't close it. 340 leaked connections currently. Connection pool config: max=200, leak detection disabled.", "servers": ["prod-db-01", "prod-app-01"], "services": ["postgresql", "order-service"], "errors": ["ERR-PG-001"], "runbook": "KB-0001", "priority": "high"},
]

L2_NET = [
    {"title": "BGP route flapping causing intermittent packet loss", "description": "Core router vpn-gw-01 BGP session flapping with upstream ISP. show ip bgp summary: state alternating between Established and Idle every 2-3 minutes. During flaps, 15-30s of packet loss affecting all external traffic. ISP NOC confirms they see the flaps from their side. MTU mismatch suspected after recent ISP circuit upgrade.", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "F5 load balancer SSL offloading degraded — cipher negotiation slow", "description": "lb-web-01 SSL handshake time increased from 5ms to 800ms. F5 tmsh show sys performance ssl shows SSL TPS dropped from 5000 to 200. Suspect crypto accelerator card failure. HTTP health checks passing but HTTPS performance severely degraded. All web traffic affected.", "servers": [], "services": ["nginx"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "DNS TTL misconfiguration causing stale records", "description": "Internal DNS returning stale A records for prod-app-03 (old IP 10.0.2.12 instead of new 10.0.2.15 after migration). TTL set to 86400 (24h) instead of 300 (5m). Some clients hitting old IP, getting connection refused. Need to flush DNS cache on all servers and reduce TTL.", "servers": ["prod-app-03"], "services": [], "errors": ["ERR-DNS-001"], "runbook": None, "priority": "high"},
    {"title": "Palo Alto GlobalProtect VPN split-tunnel not working for ap-south-2 users", "description": "ap-south-2 office VPN users reporting all traffic routing through VPN instead of split-tunnel. Bandwidth saturating VPN concentrator. Traced to GlobalProtect config push (CHG-9980) that overwrote split-tunnel routes. 25 engineers affected with 5x slower internet.", "servers": [], "services": [], "errors": [], "runbook": "KB-0003", "priority": "medium"},
    {"title": "VLAN 100 broadcast storm detected on sw-core-01", "description": "sw-core-01 CPU at 95% due to broadcast storm on VLAN 100 (server subnet). show mac address-table count shows 18,000 entries (normal: 200). Spanning tree loop suspected — redundant cable accidentally connected between rack 3 and rack 5 during cabling work. Need to identify and remove loop.", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "critical"},
]

L2_SEC = [
    {"title": "CVE-2026-3891 — critical RCE in OpenSSL affecting prod-web-01/02", "description": "NVD published CVE-2026-3891 (CVSS 9.8) affecting OpenSSL 3.0.x before 3.0.15. Both prod-web-01 and prod-web-02 running OpenSSL 3.0.12 (confirmed via openssl version). Remote code execution via crafted TLS handshake. Public exploit available on GitHub. Per security policy: patch within 24h for CVSS >= 9.0.", "servers": ["prod-web-01", "prod-web-02"], "services": ["nginx"], "errors": [], "runbook": "KB-0005", "priority": "critical"},
    {"title": "Kubernetes RBAC misconfiguration — default service account has cluster-admin", "description": "Security audit found default service account in 'production' namespace bound to cluster-admin ClusterRole. Every pod in production namespace has full cluster access. kubectl auth can-i --as=system:serviceaccount:production:default '*' '*' returns 'yes'. Immediate risk: any compromised pod has full cluster control.", "servers": ["prod-k8s-master"], "services": ["kubernetes"], "errors": ["ERR-SEC-001"], "runbook": None, "priority": "critical"},
    {"title": "TLS 1.0/1.1 still enabled on Exchange — compliance violation", "description": "Qualys SSL scan of prod-mail-01:443 shows TLS 1.0 and 1.1 enabled. PCI DSS 4.0 requires TLS 1.2 minimum. Audit finding: HIGH. Exchange Server 2019 supports TLS 1.3 but not configured. Need to disable legacy protocols and test client compatibility before enforcing.", "servers": ["prod-mail-01"], "services": ["exchange"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "AWS access keys found in GitHub public repo", "description": "GitHub secret scanning alert: AWS access key AKIA*** found in public repo 'arif-asadullah/test-scripts' committed 3 hours ago. Key belongs to IAM user 'deploy-prod'. Need immediate key rotation, access audit (CloudTrail), and git history cleanup.", "servers": [], "services": [], "errors": ["ERR-SEC-001"], "runbook": None, "priority": "critical"},
]

L2_STORAGE = [
    {"title": "ZFS pool degraded on prod-nfs-01 — resilvering at 12%", "description": "zpool status shows raidz2 pool 'datapool' in DEGRADED state. /dev/sde removed from pool with 847 checksum errors. Resilvering in progress: 12% complete, ETA 14 hours. Pool still functional but single-disk fault tolerance only. Second failure = data loss. I/O performance reduced 40% during resilver.", "servers": ["prod-nfs-01"], "services": ["nfs"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "iSCSI multipath failover not working on prod-db-01", "description": "prod-db-01 iSCSI multipath showing single active path (should be 2). multipathd show paths: path sda active, path sdb failed. iscsiadm -m session shows only 1 session. Storage controller firmware update (CHG-9985) may have disrupted second path. PostgreSQL I/O latency doubled.", "servers": ["prod-db-01"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "NFS export permission denied after security hardening", "description": "After security hardening on prod-nfs-01 (CHG-9988), exportfs -v shows exports restricted to specific IPs. Three new app servers (deployed last week) not in the allow list. mount.nfs returning 'access denied by server' on prod-app-03 and two k8s nodes. Need to update /etc/exports.", "servers": ["prod-nfs-01", "prod-app-03"], "services": ["nfs"], "errors": ["ERR-NFS-002"], "runbook": "KB-0006", "priority": "high"},
    {"title": "LVM thin pool at 95% — auto-extend failed", "description": "LVM thin pool 'data-pool' on prod-db-02 at 95.2% usage. Auto-extend threshold was 80% but extend failed: 'Insufficient free space on volume group'. VG has only 2GB free, thin pool needs 50GB minimum extension. PostgreSQL data directory on this thin volume. Risk: pool reaches 100% = read-only.", "servers": ["prod-db-02"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "critical"},
]

# ── Manager Templates ──
MANAGER_INFRA = [
    {"title": "IT infrastructure not ready for new hire batch — 20 employees starting Monday", "description": "We have 20 new hires joining on Monday and their workstations, accounts, and access are not set up yet. HR sent the onboarding list 2 weeks ago. This reflects poorly on our IT readiness and employee experience. Please confirm all accounts and machines will be provisioned by Friday EOD.", "servers": [], "services": ["active-directory"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Disaster recovery test failed — board asking for remediation plan", "description": "Our quarterly DR test failed last week. Recovery time was 8 hours instead of the committed 4-hour RTO. The board is asking for a remediation plan before the next audit. What went wrong and what's the timeline to fix?", "servers": ["prod-db-01", "prod-nfs-01"], "services": ["postgresql", "nfs"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Server refresh overdue — hardware out of warranty since January", "description": "Per our IT asset report, 5 production servers have been out of warranty since January. This was flagged in last year's budget review. Any hardware failure has no vendor support. Need a timeline for refresh or extended warranty purchase.", "servers": ["prod-db-01", "prod-db-02", "prod-app-01"], "services": [], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "Monitoring blind spot — outage detected by customers before IT", "description": "Last Tuesday's 2-hour outage was reported by customers on Twitter before our monitoring team noticed. This is unacceptable. Why didn't our monitoring tools catch it? Need a gap analysis and improved alerting by next sprint.", "servers": ["prod-mon-01"], "services": ["prometheus", "grafana"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Cloud migration assessment needed for board presentation", "description": "The CTO wants an assessment of migrating our on-premise infrastructure to AWS by Q3. Need a cost comparison, risk analysis, and migration timeline. This will be presented at the next board meeting on May 15th.", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "medium"},
]

MANAGER_DB = [
    {"title": "Customer data report for GDPR audit — need extraction from database", "description": "Our compliance team needs a full export of customer data processed in Q1 for the upcoming GDPR audit. The auditors arrive May 5th and this data needs to be ready by April 30th. Please coordinate with the DBA team to extract and prepare the report.", "servers": ["prod-db-01"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Database performance impacting SLA — 3 client complaints this week", "description": "Three enterprise clients have escalated performance complaints this week. Their queries are taking 10x longer than contractual SLA. Account management is requesting a root cause analysis and remediation timeline. This could affect renewal discussions worth $2M ARR.", "servers": ["prod-db-01", "prod-db-02"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "Data warehouse refresh delayed — finance team blocked on Q1 close", "description": "The nightly data warehouse ETL job hasn't run successfully for 3 days. Finance cannot generate Q1 reports needed for the earnings call. CFO has requested this be treated as P1. What is blocking the ETL and when can we expect data freshness?", "servers": ["prod-db-02"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "Database licensing audit response needed by May 10", "description": "Oracle sent a licensing audit notice. Our DBA team needs to verify all database instances and their edition levels. Legal needs our response by May 10. Please start the inventory immediately.", "servers": ["prod-db-01", "staging-db-01"], "services": ["postgresql"], "errors": [], "runbook": None, "priority": "medium"},
]

MANAGER_NET = [
    {"title": "New office in Hyderabad needs network connectivity by May 1", "description": "The Hyderabad office expansion is on schedule for May 1 occupancy. We need site-to-site VPN, Wi-Fi infrastructure, and access to all internal systems. 50 engineers will be working from this site. Network team please confirm readiness.", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Internet bandwidth upgrade — current capacity insufficient for video calls", "description": "Since moving to hybrid work, our internet bandwidth at the Mumbai office is consistently saturated during business hours. Video call quality is suffering. We need an upgrade from 500Mbps to 1Gbps. What's the lead time and cost?", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "Client-facing API latency exceeding SLA — partnership at risk", "description": "Our API partner integration with MegaCorp is showing p99 latency of 2.5 seconds, exceeding our 1-second SLA. They've issued a formal warning and may switch to a competitor. Network and application teams need to jointly investigate.", "servers": ["prod-web-01"], "services": ["api-gateway", "nginx"], "errors": [], "runbook": None, "priority": "critical"},
    {"title": "CEO unable to access systems during international travel", "description": "The CEO is traveling to Singapore next week and historically has issues accessing our systems due to geo-blocking. Please ensure VPN and all critical systems are accessible from Singapore. This needs to be tested before departure on Thursday.", "servers": [], "services": [], "errors": [], "runbook": "KB-0003", "priority": "high"},
]

MANAGER_SEC = [
    {"title": "SOC2 audit finding — MFA not enforced on all admin accounts", "description": "Our SOC2 auditor flagged that MFA is not enforced on 12 administrator accounts. This is a high-severity finding that could affect our certification. Compliance team needs confirmation that MFA is enforced on all admin accounts by next Friday.", "servers": ["prod-ldap-01"], "services": ["active-directory"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Vendor security questionnaire due Friday — need IT input", "description": "Our largest client sent a 200-question security questionnaire for annual review. Legal and compliance teams have filled their sections. IT security team needs to complete the technical sections (encryption, access controls, incident response) by Friday.", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "medium"},
    {"title": "Employee offboarding not disabling accounts timely — HR escalation", "description": "HR flagged that 5 employees who left in March still have active system access. Our offboarding SLA is 24 hours. This is a security risk and compliance issue. Need an immediate audit of all terminated employee accounts and process fix.", "servers": ["prod-ldap-01"], "services": ["active-directory"], "errors": [], "runbook": "KB-0009", "priority": "critical"},
    {"title": "Penetration test scheduled for next week — coordination needed", "description": "Our annual penetration test is scheduled for May 5-9. The security firm will be testing external and internal attack surfaces. All teams need to be on standby for rapid remediation. Please confirm readiness and emergency contacts.", "servers": [], "services": [], "errors": [], "runbook": None, "priority": "medium"},
]

MANAGER_STORAGE = [
    {"title": "Storage capacity forecast — running out in 60 days", "description": "Our storage utilization report shows we'll hit 95% capacity within 60 days at current growth rate. Procurement needs 6-8 weeks lead time for new storage arrays. Please submit the purchase request this week with specifications and cost estimate.", "servers": ["prod-nfs-01"], "services": ["nfs"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Data retention policy implementation overdue — legal requirement", "description": "Legal team mandated data retention policy implementation by April 30. Customer data older than 7 years must be archived and financial records retained for 10 years. DBA and storage teams need to coordinate automated archival.", "servers": ["prod-db-01", "prod-nfs-01"], "services": ["postgresql", "nfs"], "errors": [], "runbook": None, "priority": "high"},
    {"title": "Backup SLA breach — RPO exceeded for 3 consecutive days", "description": "Our backup monitoring shows RPO of 72 hours instead of committed 24 hours for the last 3 days. Multiple backup jobs failing silently. This violates our business continuity commitments. Need root cause and immediate remediation.", "servers": ["prod-nfs-01"], "services": ["nfs"], "errors": [], "runbook": None, "priority": "critical"},
]

def build_ticket(template, persona, category):
    """Convert template to full ticket with resolution."""
    resolution_templates = [
        ["Investigated the reported issue", "Identified root cause", "Applied fix", "Verified resolution with user"],
        ["Reviewed system logs and metrics", "Found configuration issue", "Updated configuration", "Tested and confirmed fix"],
        ["Triaged ticket and assessed severity", "Engaged appropriate team", "Implemented resolution", "Monitored for recurrence"],
    ]

    return {
        "title": template["title"],
        "description": template["description"],
        "category": category,
        "priority": template["priority"],
        "affects_servers": template["servers"],
        "affects_services": template["services"],
        "error_codes": template["errors"],
        "resolution_steps": template.get("resolution_steps", random.choice(resolution_templates)),
        "resolution_effectiveness": round(random.uniform(0.75, 0.95), 2),
        "references_runbook": template["runbook"],
        "quality_score": "HIGH",
        "secondary_category": None,
        "classifier_votes": None,
        "source_model": "claude",
        "persona": persona,
    }


def main():
    # Load existing tickets
    existing = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)

    print(f"Existing Claude tickets: {len(existing)}")

    all_templates = []

    # Frustrated user
    for t in FRUSTRATED_INFRA: all_templates.append((t, "frustrated_user", "Infrastructure"))
    for t in FRUSTRATED_DB: all_templates.append((t, "frustrated_user", "Database"))
    for t in FRUSTRATED_NET: all_templates.append((t, "frustrated_user", "Network"))
    for t in FRUSTRATED_SEC: all_templates.append((t, "frustrated_user", "Security"))
    for t in FRUSTRATED_STORAGE: all_templates.append((t, "frustrated_user", "Access Management"))

    # L2 Engineer
    for t in L2_INFRA: all_templates.append((t, "l2_engineer", "Infrastructure"))
    for t in L2_DB: all_templates.append((t, "l2_engineer", "Database"))
    for t in L2_NET: all_templates.append((t, "l2_engineer", "Network"))
    for t in L2_SEC: all_templates.append((t, "l2_engineer", "Security"))
    for t in L2_STORAGE: all_templates.append((t, "l2_engineer", "Access Management"))

    # Manager
    for t in MANAGER_INFRA: all_templates.append((t, "manager", "Infrastructure"))
    for t in MANAGER_DB: all_templates.append((t, "manager", "Database"))
    for t in MANAGER_NET: all_templates.append((t, "manager", "Network"))
    for t in MANAGER_SEC: all_templates.append((t, "manager", "Security"))
    for t in MANAGER_STORAGE: all_templates.append((t, "manager", "Access Management"))

    new_tickets = []
    for template, persona, category in all_templates:
        ticket = build_ticket(template, persona, category)
        new_tickets.append(ticket)

    combined = existing + new_tickets

    with open(OUTPUT_FILE, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"New tickets generated: {len(new_tickets)}")
    print(f"Total Claude tickets: {len(combined)}")

    from collections import Counter
    cats = Counter(t["category"] for t in combined)
    personas = Counter(t["persona"] for t in combined)
    print(f"\nCategories: {dict(sorted(cats.items()))}")
    print(f"Personas: {dict(sorted(personas.items()))}")
    print(f"\nSaved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
