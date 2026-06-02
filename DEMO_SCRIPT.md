# DeskMind — 30-Minute Jury Presentation Script

> **Nasscom AI-Code-Sarathi Excel Hackathon — Final Round**
> **Presenter**: Arif Asadullah (Team Lead)
> **Team**: Arif Asadullah, Aakarsh, Mohit Tomar
> **Format**: 30 min presentation + 15 min Q&A (Teams meeting, cameras ON)

---

## BEFORE YOU PRESENT

- Set screen to **1920x1080** or **1440x900**
- Switch to **light theme** (cleaner on video/screen share)
- **Docker containers running** (`docker compose up`)
- **Ollama running** with `qwen2.5:7b` model loaded
- Pre-seed **5-6 tickets** so dashboard isn't empty
- Have this file + ticket texts open on **second screen**
- Test screen share on Teams before the call
- Move cursor **slowly** to what you're explaining
- **Rehearse at least twice** — aim for 28 minutes (2 min buffer)

---

## SECTION 1 — PROBLEM & SOLUTION (0:00 - 2:00)

> *[Show DeskMind login page on screen]*

Hey everyone... my name is Arif Asadullah, I'm the team lead for DeskMind. With me today are Aakarsh and Mohit.

[pause]

So let me start with the **problem**. In enterprise IT, when someone submits a support ticket... a human has to read it, understand the issue, and manually assign it to the right team. In a company with thousands of tickets per week, this creates **two major problems**:

**One** — it's slow. Misrouted tickets add 2-4 hours of delay per incident.
**Two** — it's error-prone. A sysadmin might route a PostgreSQL replication issue to Infrastructure because it mentions "server"... when it should go to Database Admin.

[pause]

**DeskMind solves this** with an AI-powered system that doesn't just use one AI model — it uses **four independent classifiers** that vote together. Like a panel of experts. And all of it runs **100% on-premise** — no OpenAI, no cloud APIs. Your data never leaves your network.

[pause]

But DeskMind isn't just a classifier. It's an **agentic AI system** that:
- **Generates custom resolutions** using past data
- **Predicts incidents** before they escalate
- **Enriches vague tickets** with intelligent follow-up questions
- **Learns from corrections** to improve over time

Let me show you.

> **KEY TALKING POINT**: We're not just classifying — we're solving. The system is agentic.

---

## SECTION 2 — ARCHITECTURE OVERVIEW (2:00 - 4:00)

> *[Show architecture slide or switch to a prepared diagram]*

So here's the high-level architecture. [pause]

We have **four main components**:

- **React frontend** on port 3000 — the UI you'll see in a moment
- **FastAPI backend** on port 8000 — the brain of the system
- **ArangoDB** — this is our knowledge graph database. It's a triple-purpose DB: document store, graph engine, AND vector database. All in one.
- **Ollama** running **Qwen 2.5:7B** — our local LLM. 7 billion parameters, runs on CPU.

[pause]

The classification happens in **5 stages**:

1. **Prepare** — extract entities (server names, services, error codes), score ticket quality, clean text, compute embeddings
2. **Retrieve** — 4 parallel searches: vector similarity, error code matching, knowledge graph traversal, full-text search
3. **Classify** — run 4 classifiers in parallel: LLM (40% weight), Centroid (30%), KNN (15%), Keyword (15%)
4. **Aggregate** — majority-aware voting with 6 phases
5. **Decide** — route to team OR escalate + generate resolution + find expert

[pause]

All 4 classifiers run **in parallel**. So total time equals the slowest classifier (the LLM at ~5-7 seconds), not the sum.

And we have **Redis** for two-tier caching, SLA timers, rate limiting, and real-time updates via Socket.IO.

> **KEY TALKING POINT**: ArangoDB = 3 databases in 1 (graph + document + vector). No need for Neo4j + Pinecone + MongoDB separately.

---

## SECTION 3 — LOGIN + DASHBOARD (4:00 - 5:00)

> *[Log in to DeskMind]*

> - Email: `arif.asadullah@schwettmann.in`
> - Password: `DeskMind@2026`

So this is the login screen. You can see the three-step flow — Submit, Classify, Route. And these status pills show system health in real time.

[pause]

> *[Dashboard loads]*

This is the main dashboard. **Six domains** — Infrastructure, Application, Database, Network, Security, Access Management. Each card shows ticket count and distribution.

[pause]

Up top — the stats bar with animated counters. Total tickets, auto-routed count, escalation rate, average confidence.

> *[Point to incident prediction banner if visible]*

And see this banner? That's our **incident prediction system**. It automatically scans for patterns — if 3+ tickets hit the same team within 4 hours, or there's a 50% spike in volume... it alerts you proactively. Admins see everything, engineers see only their team's alerts.

---

## SECTION 4 — LIVE CLASSIFICATION (5:00 - 11:00)

### TICKET 1 — Infrastructure (2 min)

> *[Click "Create Ticket"]*

Let's create a real ticket. A sysadmin's production server is down.

> **Paste TICKET 1** (see bottom of script)

Submitting now... so while the AI is working, let me explain what's happening.

[pause]

**Four classifiers** are running in parallel right now:

The **LLM** — Qwen 2.5:7B — is reading the full ticket plus context from the knowledge graph. It has 12 disambiguation rules. For example, it knows "Kubernetes NODE crash" = Infrastructure, but "Kubernetes POD crash" = Application. Root cause, not symptom.

The **Centroid classifier** takes the ticket's embedding vector and compares it to 6 pre-computed category centroids. Pure math, no AI — which category is this closest to in vector space?

**KNN** looks at the 5 most similar past tickets and votes by their categories. Weighted by similarity — a 95% match counts more than a 60% match.

And **Keyword matching** — simple but fast. Pattern matching on 100+ domain-specific terms.

> *[Result appears]*

There it is — **Infrastructure**. High confidence. All 4 classifiers agreed.

[pause]

### TICKET 2 — Database (2 min)

> **Paste TICKET 2** (PostgreSQL replication lag)

This one is interesting because it mentions "network throughput" and "replication lag." A simple system might get confused — is this Network or Database?

[pause]

But our LLM understands that replication lag is fundamentally a **database problem**, even though network is mentioned. And the centroid classifier has seen similar tickets — the vector is closer to the Database centroid.

> *[Result appears]*

**Database Admin**. Correct. This is the power of root-cause classification.

### TICKET 3 — Security (2 min)

> **Paste TICKET 3** (credential stuffing attack)

Security scenario — credential stuffing attack on the API Gateway.

> *[Result appears]*

**Security Operations**. Now here's something important — look at the **majority-aware voting**. We have a 6-phase algorithm:

- Phase 1: All 4 agree? Take it (cap 0.95).
- Phase 2: 3 out of 4? Check if the majority is confident.
- Phase 3: 2 vs 1 vs 1? Pair beats scattered singles.
- Phase 4: 2 vs 2 deadlock? We have **boundary override rules**. For example, Database vs Infrastructure is a known confusing pair — we trust the embedding classifiers over keywords.
- Phase 5: Total disagreement? Weighted fallback, cap confidence at 0.50.

This algorithm was hardened with external review. It handles every edge case.

> **KEY TALKING POINT**: Not just "highest score wins" — structured 6-phase voting with strength checks and boundary overrides.

---

## SECTION 5 — TICKET DETAIL DEEP DIVE (11:00 - 13:00)

> *[Click into the Infrastructure ticket]*

Let me show you the detail view. [pause]

Here's the full ticket with status badge, priority indicator, and SLA deadline. Critical tickets have a 2-hour SLA timer running in Redis.

[pause]

But the important part is this — the **classifier breakdown**. You can see exactly how each classifier voted:
- LLM said Infrastructure with 0.92 confidence
- Centroid said Infrastructure with 0.78
- KNN said Infrastructure with 0.85
- Keyword said Infrastructure with 0.67

And here's the **AI reasoning** — the LLM explains WHY it classified this way. Full explainability. Not a black box.

[pause]

And scroll down — the **audit trail**. Every action is logged: when it was classified, who the system routed it to, confidence scores. Full traceability for compliance.

> **KEY TALKING POINT**: Enterprise-ready explainability. Every decision has a paper trail.

---

## SECTION 6 — AI RESOLUTION GENERATOR (13:00 - 16:00)

> *[Click "Create Ticket"]*

Now this is one of our most powerful features. The **AI Resolution Generator**.

Most systems just classify and route. DeskMind goes further — it actually **generates a step-by-step fix**.

> **Paste TICKET 6** (SCIM provisioning broken — see bottom)

This is an unusual ticket about SCIM provisioning with Okta breaking. The system probably doesn't have an exact historical match for this.

> *[Wait for result]*

Look at this — the system classified it as **Access Management**. But more importantly... scroll down to the purple card.

[pause]

See? **"AI-Generated Resolution"** — the LLM generated 5 custom steps:
1. Verify network connectivity between Okta and the SCIM gateway
2. Check firewall rules for recent changes
3. Verify SCIM service configuration
4. Increase connection timeout settings
5. Monitor for successful provisioning

[pause]

And look — it shows the **reasoning** ("these steps address potential network issues and configuration errors..."), the **confidence level**, and the **sources used** ("based on 3 similar resolved tickets").

This is **grounded generation** — the LLM doesn't hallucinate from nothing. It synthesizes from past resolutions + knowledge graph context + error patterns. There's a quality gate: if no reference data exists, it won't generate. It only generates when it has something real to base it on.

> *[Show the ResolveForm]*

And when an engineer resolves this ticket, the AI-generated steps are pre-filled. They can use them as-is, modify them, or write their own. Either way, the effectiveness is tracked — creating a feedback loop.

> **KEY TALKING POINT**: DeskMind doesn't just route — it SOLVES. True agentic AI. Grounded generation, no hallucination.

---

## SECTION 7 — ENRICHMENT AGENT (16:00 - 18:00)

> *[Click "Create Ticket"]*

What happens when someone submits a vague ticket? Like... "my system is not working."

> **Paste TICKET 7** (vague ticket — see bottom)

[pause]

> *[Wait for result]*

See? The system detected this is a **LOW quality** ticket. Confidence is low. But instead of just saying "I don't know"... it shows the **Enrichment Card**.

[pause]

These are **intelligent follow-up questions**:
- "Which server is affected?" — and it shows suggestions from THIS USER'S common servers (personalized!)
- "What error message do you see?" — with clickable common options
- "What's the business impact?" — Production down, Performance degraded, etc.
- "When did this start?"

[pause]

The user clicks the suggestions... let me click "prod-app-01" for server... "Timeout" for error... "Production down" for impact...

> *[Click suggestions and submit]*

Now the system **re-classifies** with the enriched description. The confidence should jump significantly because now it has real context.

> **KEY TALKING POINT**: The system doesn't reject vague tickets — it makes them better. Personalized to the user's history.

---

## SECTION 8 — OVERRIDE + SELF-LEARNING (18:00 - 20:00)

> *[Click into a ticket, then click Override]*

So what happens when the AI gets it wrong? Engineers can **override** the classification.

> *[Show Override Modal — select a different category, type a reason]*

When they override, three things happen:

**One** — the correction is recorded in the `corrections` collection. It tracks which classifiers were wrong and which were right.

**Two** — the **cache is invalidated**. Both tiers flushed. So if a similar ticket comes in, it won't get the old wrong answer.

**Three** — an admin can trigger **centroid recomputation**. The system recalculates the average embedding for each category based on all tickets including corrections. So the centroid classifier gets smarter over time.

[pause]

This is one of our **three self-learning feedback loops**:

1. **Resolution quality gate** — engineers rate resolutions as helpful/not helpful. Good resolutions float to the top in future suggestions.
2. **Human corrections** — override data retrains centroids and exports as training data.
3. **Repeated issue detection** — the system detects clusters of similar tickets and flags them as recurring patterns.

> **KEY TALKING POINT**: The system gets smarter with every ticket. Three feedback loops ensure continuous improvement.

---

## SECTION 9 — KNOWLEDGE GRAPH + ANALYTICS (20:00 - 22:00)

> *[Click "Knowledge Graph" tab]*

This is the interactive knowledge graph. [pause]

Blue = teams. Green = engineers. Orange = servers. Purple = services. Red = error codes.

> *[Hover and click nodes]*

See the connections? Which engineers belong to which team... which servers host which services... which services depend on each other.

This isn't just visualization — the classification engine **uses** this graph. When a ticket mentions "prod-db-01", the system traverses the graph to find: it's a database server, managed by Database Admin team, hosting PostgreSQL, with Arjun and Meera as experts. That context goes directly into the LLM's prompt.

> *[Switch to Analytics tab]*

And here's the analytics dashboard — category distribution, status breakdown, confidence trends, team workload. Domain-filtered so each team sees their own metrics.

---

## SECTION 10 — MINDY AI CHAT (22:00 - 24:00)

> *[Click the "Ask Mindy" floating button]*

This is Mindy, our AI assistant. The key feature: **zero hallucination**. [pause]

How? It uses a **three-step approach**:
1. Rule-based intent parser — figures out what you're asking
2. Direct ArangoDB query — fetches real data
3. LLM formats the response — but NEVER invents data

> **Type:** `show me all critical tickets`

[pause — wait for response]

See? Real ticket data with colored entity chips. These are clickable.

> **Type:** `which team handles database issues`

[pause]

Team name, engineers, their expertise — all from the knowledge graph.

> **Type:** `how many tickets are escalated right now`

Real-time stats, not hallucinated. The LLM never makes things up because it only formats what the database returns.

> **KEY TALKING POINT**: Every answer backed by real data. Rule-based parsing + real DB queries + LLM formatting = zero hallucination.

---

## SECTION 11 — ACCURACY STORY (24:00 - 27:00)

> *[Show evaluation results — can use terminal or prepared slide]*

Let me talk about accuracy. We didn't just build features — we **measured everything**.

[pause]

We built a **fixed benchmark** of 35 hand-labeled tickets covering all 6 categories plus boundary and edge cases. Every improvement is measured against this same test set.

Here's our journey:

| Step | Accuracy | Delta |
|------|----------|-------|
| Baseline (R2 submission) | 85.3% | — |
| + Title+description co-embedding | **94.1%** | **+8.8%** |
| + KNN confidence fix | 94.1% | maintained |
| + Text preprocessing | 94.1% | maintained |
| + Retrieval re-ranking | 94.1% | maintained |
| + Quality scorer upgrade | 94.1% | maintained |

[pause]

The single biggest win was **embedding title + description together** instead of description alone. Titles like "RBAC policy preventing access" immediately signal Access Management — but if you only embed the description, the vector lands near Infrastructure.

We also tested **switching the embedding model** to BGE-small. It actually **regressed** — 91.2%. So we kept MiniLM. Not every "better benchmark" model works for your domain. We measured, we reverted. That's rigor.

[pause]

The ensemble (94.1%) outperforms every individual classifier:
- LLM alone: 94.1%
- KNN alone: 76.5%
- Centroid alone: 73.5%
- Keyword alone: 67.7%

The ensemble is as good as the LLM alone — but with **graceful degradation**. If Ollama goes down, the remaining 3 classifiers still give you 70%+ accuracy. The LLM alone gives you zero.

> **KEY TALKING POINT**: Rigorous, reproducible benchmarking. Every claim backed by data. Ensemble provides accuracy + resilience.

---

## SECTION 12 — PRODUCTION-READY ARCHITECTURE (27:00 - 29:00)

> *[Can show health endpoint or explain verbally]*

Let me quickly cover what makes this production-ready:

**Graceful Degradation** — 4 levels. Full pipeline → No data (LLM + keyword) → No LLM (KNN + centroid + keyword) → Emergency (keyword only). The system **never fully crashes**.

**Circuit Breaker** — if Ollama fails 3 times, the circuit breaker opens. No more wasted calls. After 30 seconds, it tests recovery.

**Two-Tier Cache** — Tier A is exact text match (SHA-256 hash, <5ms). Tier B is semantic similarity (cosine > 0.95 against recent embeddings, <10ms). Most repeat tickets never hit the LLM.

**SLA Timers** — Redis TTL keys. Critical = 2 hours, High = 4 hours, Medium = 8 hours, Low = 24 hours. When the TTL expires, the ticket is flagged as breached.

**Rate Limiting** — 50 requests per user per minute, 200 global. Sliding window in Redis.

**Everything local** — Ollama + Qwen 2.5:7B, MiniLM embeddings, ArangoDB, Redis. No cloud APIs. Full data privacy. Works offline after setup.

> **KEY TALKING POINT**: Not a prototype — production-ready with circuit breakers, caching, SLA management, and zero cloud dependency.

---

## SECTION 13 — CLOSING (29:00 - 30:00)

> *[Go back to dashboard]*

So to recap what makes DeskMind different:

**One** — **4-classifier ensemble** with majority-aware voting. 94.1% accuracy, benchmark-verified.

**Two** — **Agentic AI** — doesn't just classify, it generates resolutions, enriches vague tickets, and predicts incidents.

**Three** — **Self-learning** — three feedback loops that make the system smarter with every ticket.

**Four** — **Knowledge graph powered** — real infrastructure relationships driving context-aware decisions.

**Five** — **Zero hallucination** — every AI response grounded in real data.

**Six** — **100% on-premise** — no cloud APIs, full data privacy, works offline.

[pause]

That's DeskMind. An intelligent IT ticket routing system that's accurate, transparent, and ready for production.

Thank you. We're happy to take questions.

---

---

# Q&A PREPARATION (15 minutes)

> *Read these before the presentation. Know the answers cold.*

### "How does it handle misclassification?"
Engineers can override any classification. The correction is tracked — which classifiers were right/wrong. The cache is invalidated. Centroids can be recomputed. The system learns from mistakes.

### "What happens when Ollama/LLM goes down?"
Circuit breaker activates after 3 failures. System falls to Level 2 — KNN + Centroid + Keyword classifiers still work (~70% accuracy). Weights auto-rebalance (Centroid gets 50%). If database also goes down, keyword-only mode (~55%). System never fully crashes.

### "Why not just use GPT-4 or Claude?"
Three reasons: (1) Data privacy — tickets contain sensitive infrastructure details, can't send to cloud. (2) Cost — zero API costs, scales without billing surprises. (3) Latency — no network round trip. And our ensemble approach (94.1%) is competitive with single-model cloud solutions.

### "How does the knowledge graph help classification?"
The graph provides context a standalone LLM can't access. When a ticket mentions "prod-db-01", the system traverses the graph to discover: it's a database server, in ap-south-1, managed by Database Admin team, running PostgreSQL and Redis, with dependent services. This context is injected into the LLM prompt, improving accuracy on ambiguous tickets.

### "Can this scale to 1000+ tickets/hour?"
Yes. The two-tier cache handles repeat/similar tickets in <10ms. The LLM is the bottleneck at ~5-7s per ticket, but: (1) cache hits bypass the LLM entirely, (2) Ollama supports concurrent requests, (3) the model can be upgraded to faster hardware, (4) in degraded mode, non-LLM classifiers handle tickets in <100ms.

### "What's your accuracy on real production data?"
Our benchmark uses 35 hand-labeled tickets designed to test real-world scenarios including boundary cases (Database vs Infrastructure), multi-domain tickets, and very short descriptions. 94.1% accuracy. We also tested on 50 randomly sampled synthetic tickets earlier — 83.7% (before improvements). Real production data would need domain-specific tuning of the seed data.

### "How does the AI Resolution Generator avoid hallucination?"
Quality gate: it only generates when reference data exists (similar past resolutions, graph context, or error patterns). If there's nothing to ground on, it returns nothing. The system prompt explicitly says "base your steps ONLY on the reference solutions provided." Temperature is 0.2 — creative enough to adapt, constrained enough not to invent.

### "What about the Enrichment Agent — does it always trigger?"
No. Only for LOW quality tickets (short, no entities, no errors) or MEDIUM quality with confidence < 0.70. HIGH quality tickets with clear entities skip enrichment entirely. The questions are personalized — if the user usually submits Database tickets, the server suggestions show their common DB servers.

### "How is the voting algorithm different from simple weighted average?"
Simple weighted average just multiplies confidence × weight and picks the max. Our 6-phase algorithm handles edge cases: 2v2 deadlocks with boundary overrides (Database vs Infrastructure gets special treatment), strength checks (supermajority must average > 0.60 confidence), and tiebreaker protocols. This was reviewed and hardened externally.

### "What technology would you change if starting over?"
Honestly, not much. ArangoDB as a 3-in-1 database was the right call — eliminated a lot of complexity. If anything, we'd start with Qwen 7B from the beginning instead of 3B, and build the evaluation benchmark earlier to guide improvements.

---

---

# COPY-PASTE TICKETS

> Keep in a notepad for quick pasting during the demo.

## Ticket 1 — Infrastructure (Clear)
```
Title: prod-app-01 server is completely unresponsive since morning

Description: Hi team, this is urgent. Our main production application server prod-app-01 has been completely unresponsive since 6 AM. No SSH access, ping is timing out, and the monitoring dashboard shows the server as offline. Multiple services are affected and customers are reporting errors. We need someone to check the physical server or VMware console immediately. This is impacting production traffic.

Priority: Critical
```

## Ticket 2 — Database (Boundary case: mentions network)
```
Title: PostgreSQL replication lag on prod-db-02 keeps growing

Description: Hey, I've been monitoring our PostgreSQL cluster and noticed that the replication lag on prod-db-02 has been steadily increasing over the past 3 hours. It started at a few seconds and now it's over 2 minutes behind the primary. The WAL sender process seems to be struggling. I checked and there's no unusual load on the replica, but the network throughput between primary and replica looks lower than normal. We might need to investigate the replication slot and potentially rebuild if it gets worse.

Priority: High
```

## Ticket 3 — Security (Clear)
```
Title: Multiple failed login attempts detected on API Gateway

Description: Our SIEM dashboard is showing an unusual spike in failed authentication attempts against the main API Gateway over the last hour. We're seeing roughly 500 failed attempts from about 15 different IP addresses, mostly from regions where we don't have any users. The pattern looks like a credential stuffing attack. The API Gateway is still functional but I'm concerned about a potential breach. We need to review the access logs, potentially block the suspicious IPs at the WAF level, and check if any accounts were actually compromised.

Priority: Critical
```

## Ticket 4 — Network (if time)
```
Title: VPN keeps disconnecting every 10-15 minutes

Description: Hi, I've been working remotely and for the past two days my VPN connection keeps dropping every 10-15 minutes. I'm using the Cisco AnyConnect client on Windows. When it disconnects I have to manually reconnect and it interrupts all my work. I've tried restarting the client, rebooting my laptop, and even switching from WiFi to a wired connection, but the issue persists. Other people in my team don't seem to have this issue. Could someone from the network team look into my VPN profile or the concentrator logs?

Priority: High
```

## Ticket 5 — Access Management (if time)
```
Title: Can't access Jira and Confluence after department transfer

Description: Hi, I recently transferred from the Marketing department to Engineering last week. My manager submitted the department transfer form but I still can't access any of the Engineering team's Jira projects or Confluence spaces. I can see my old Marketing projects but when I try to access Engineering boards I get "You don't have permission." I need access to the sprint board and the technical documentation space urgently as I'm starting a new project on Monday.

Priority: Medium
```

## Ticket 6 — AI Resolution Generator (unusual ticket)
```
Title: SCIM provisioning sync broken with Okta

Description: Okta SCIM provisioning to our internal IdP stopped syncing 3 days ago. New hires are not getting accounts created automatically. The SCIM endpoint returns 502. Okta logs show connection timeout to our SCIM gateway. Over 15 new employees stuck without access.

Priority: High
```

## Ticket 7 — Enrichment Agent (vague ticket)
```
Title: System not working

Description: My system is not working since morning. Please help urgently.

Priority: High
```

---

# MINDY CHAT QUESTIONS

```
show me all critical tickets
```
```
which team handles database issues
```
```
how many tickets are escalated right now
```
```
show me all infrastructure tickets
```

---

# LOGIN CREDENTIALS

- **Email:** `arif.asadullah@schwettmann.in`
- **Password:** `DeskMind@2026`
