# DeskMind — Jury Presentation Slides

> **Instructions**: Paste this entire file into Claude web chat with the prompt:
> "Create a professional PowerPoint presentation from this content. Use a dark theme with orange (#F97316) accents. Make it visually clean and modern. 12 slides."

---

## SLIDE 1: Title Slide

**Title**: DeskMind
**Subtitle**: AI-Powered IT Ticket Routing & Resolution System
**Bottom text**: Nasscom AI-Code-Sarathi Excel Hackathon — Final Round
**Team**: Arif Asadullah (Lead) | Aakarsh | Mohit Tomar
**Date**: June 2026

**Visual**: DeskMind logo centered, dark background, subtle tech pattern

---

## SLIDE 2: The Problem

**Title**: The Problem: Manual Ticket Triage is Broken

**Left side — Pain Points:**
- L1 support staff manually read and route every ticket
- Misrouted tickets add **2-4 hours** of delay per incident
- Critical issues get lost in queues
- Knowledge trapped in individual heads, not systems
- No learning from past resolutions

**Right side — Impact Numbers:**
- 40% of tickets misrouted on first attempt (industry average)
- $15-25 cost per manual triage decision
- Engineers waste time on wrong-domain tickets

**Speaker Notes**: Start with the problem. Every enterprise faces this. The cost isn't just time — it's frustrated employees, delayed fixes, and repeated incidents.

---

## SLIDE 3: Our Solution

**Title**: DeskMind: Not Just Classification — Agentic AI

**Key message (large text)**: "DeskMind doesn't just route tickets. It SOLVES them."

**4 pillars (with icons):**
1. **Classify** — 4-classifier ensemble, 94.1% accuracy
2. **Generate** — AI creates custom step-by-step resolutions
3. **Predict** — Detects incidents before they escalate
4. **Learn** — Gets smarter with every ticket (3 feedback loops)

**Bottom**: 100% on-premise | Zero cloud APIs | Full data privacy

**Speaker Notes**: This is our differentiator. Most teams just classify. We go further — resolution generation, incident prediction, self-learning. Truly agentic.

---

## SLIDE 4: Architecture

**Title**: System Architecture

**Diagram showing 4 components:**
- React Frontend (26 components)
- FastAPI Backend (24 services, 32 API endpoints)
- ArangoDB 3.12 (Graph + Vector + Document — 3-in-1 database)
- Ollama + Qwen 2.5:7B (Local LLM, no cloud)
- Redis 7 (Cache + SLA + Rate Limiting)

**5-Stage Pipeline (horizontal flow):**
Stage 1: PREPARE (entities, quality, embedding) →
Stage 2: RETRIEVE (vector + error + graph + fulltext) →
Stage 3: CLASSIFY (4 classifiers in parallel) →
Stage 4: AGGREGATE (6-phase majority-aware voting) →
Stage 5: DECIDE (route + generate resolution + enrich)

**Key callout**: "ArangoDB = Neo4j + Pinecone + MongoDB in one engine"

**Speaker Notes**: Highlight ArangoDB as a 3-in-1 database. All 4 classifiers run in parallel — total time = LLM time only (~5-7s). Mention that everything runs locally.

---

## SLIDE 5: 4-Classifier Ensemble

**Title**: 4 Classifiers Vote Together — Like a Panel of Experts

**Table:**
| Classifier | Weight | What it Does | Accuracy Alone |
|-----------|--------|-------------|----------------|
| LLM (Qwen 2.5:7B) | 40% | Reads full context, reasons about root cause | 94.1% |
| Centroid | 30% | Compares embedding to category centers | 73.5% |
| KNN | 15% | 5 similar past tickets vote by category | 76.5% |
| Keyword | 15% | Pattern matching on 100+ domain terms | 67.7% |

**Key insight (highlighted box)**:
"Ensemble accuracy (94.1%) matches the best individual classifier — but with graceful degradation. If LLM goes down, remaining 3 classifiers still achieve ~70% (projected)."

**Bottom**: Majority-Aware Voting: 6-phase algorithm with boundary overrides, strength checks, and tiebreaker protocols

**Speaker Notes**: Explain why ensemble > single model. The LLM is smart but fragile. Ensemble gives you accuracy + resilience. Mention the 6-phase voting was reviewed and hardened.

---

## SLIDE 6: Accuracy Results

**Title**: 94.1% Accuracy — Benchmark Verified

**Left side — Per Category:**
| Category | Accuracy |
|----------|----------|
| Infrastructure | 100% |
| Network | 100% |
| Security | 100% |
| Access Management | 100% |
| Application | 85.7% |
| Database | 83.3% |

**Right side — Improvement Journey:**
| Step | Accuracy | Delta |
|------|----------|-------|
| Baseline (R2) | 85.3% | — |
| + Title embedding | **94.1%** | **+8.8%** |
| + KNN fix | 94.1% | maintained |
| + BGE model (reverted) | 91.2% | -2.9% |
| + Preprocessing | 94.1% | maintained |
| + Quality scorer | **94.1%** | final |

**Key callout**: "We tested BGE-small embedding model. It regressed. We measured, we reverted. That's scientific rigor."

**Bottom**: Fixed 35-ticket benchmark with clear + boundary + edge cases. Every claim backed by data.

**Speaker Notes**: This slide is powerful for judges. Show that we don't just build features — we measure everything. The BGE revert story shows intellectual honesty.

---

## SLIDE 7: AI Resolution Generator

**Title**: Beyond Classification — AI Generates Custom Fixes

**Flow diagram:**
```
No good historical resolution found?
    ↓
AI Resolution Generator activates
    ↓
LLM reads: similar past resolutions + knowledge graph + error patterns
    ↓
Generates 3-7 actionable steps + reasoning + sources
    ↓
Engineer verifies → feedback loop → system improves
```

**Example output:**
- Ticket: "SCIM provisioning sync broken with Okta"
- AI Generated Steps:
  1. Verify network connectivity between Okta and SCIM gateway
  2. Check firewall rules for recent changes
  3. Verify SCIM service configuration and credentials
  4. Increase connection timeout settings in Okta
  5. Monitor for successful provisioning

**Quality Gate**: "Only generates when reference data exists. Hallucination-resistant."

**Speaker Notes**: This is the "wow" feature. Most systems just route — we SOLVE. Explain the quality gate: grounded generation, not guessing. If no reference data, returns nothing.

---

## SLIDE 8: Intelligent Features

**Title**: Agentic AI Features

**4 feature cards (2x2 grid):**

**Card 1 — Enrichment Agent**
- Detects vague tickets ("system not working")
- Generates personalized follow-up questions
- Suggestions from user's ticket history
- Re-classifies with enriched context

**Card 2 — Incident Prediction**
- Cluster: 3+ tickets → same team in 4 hours
- Trend: 50%+ volume increase week-over-week
- Spike: 5+ new tickets in 1 hour
- Role-filtered: admin sees all, engineer sees own team

**Card 3 — Self-Learning (3 Loops)**
- Loop 1: Resolution feedback → effectiveness scoring
- Loop 2: Human corrections → centroid retraining
- Loop 3: Repeated issue detection → pattern alerts

**Card 4 — OCR Screenshot Analysis**
- Tesseract extracts text from uploaded screenshots
- Detects type: stack trace, HTTP error, log, terminal
- Extracted entities feed into all 4 classifiers

**Speaker Notes**: Each card is 30 seconds. These differentiate us from teams that only do classification.

---

## SLIDE 9: Knowledge Graph

**Title**: Knowledge Graph — The Brain of DeskMind

**Visual**: Force-directed graph showing nodes and edges

**Stats:**
- 15 document collections, 9 edge collections
- ~3,500 edges connecting the IT organization (generated at seed time)
- 855 tickets with embeddings (55 seed + 800 synthetic)

**How it helps classification:**
- Ticket mentions "prod-db-01" → graph reveals:
  - Server type: database
  - Managed by: Database Admin team
  - Hosts: PostgreSQL, Redis
  - Experts: Arjun Nair, Meera Patel
  - Past issues: 5 similar tickets resolved
- This context injected into LLM prompt → better accuracy

**Bottom**: "Not just visualization — the graph powers classification decisions"

**Speaker Notes**: Click through the graph during live demo. Show how hovering reveals connections. Emphasize that the graph is actively used during classification, not just eye candy.

---

## SLIDE 10: Production-Ready Architecture

**Title**: Built for Production, Not Just Demo

**6 features (icons + one-liner each):**

1. **Graceful Degradation** — 4 levels of fallback. System never fully crashes.
2. **Circuit Breaker** — Ollama fast-fail after 3 failures, 30s recovery.
3. **Two-Tier Cache** — Exact match (<5ms) + semantic similarity (<10ms).
4. **SLA Timers** — Redis TTL: Critical=2h, High=4h, Medium=8h, Low=24h.
5. **Rate Limiting** — 50/user/min, 200/global. Redis sliding window.
6. **Zero Cloud Dependency** — Ollama + Qwen 2.5:7B. Full data privacy.

**Key callout**: "Cache invalidation on corrections — stale results never served after a human override"

**Speaker Notes**: Judges want to know this isn't a toy. These are production patterns. Mention that the cache alone handles repeat tickets without touching the LLM.

---

## SLIDE 11: Hallucination-Resistant Chat

**Title**: Mindy AI — Hallucination-Resistant Conversational AI

**3-step approach (flow diagram):**
1. **Rule-based Intent Parser** — Understands what you're asking (no LLM needed)
2. **ArangoDB Query** — Fetches real data from the database
3. **LLM Formats** — Makes the response human-readable (never invents data)

**Example queries:**
- "Show me all critical tickets" → Real ticket data with entity chips
- "Which team handles database issues?" → Database Admin team + engineers
- "How many tickets are escalated?" → Real-time count from DB

**Key callout**: "The LLM doesn't invent data — it never has to. It only formats what the database returns."

**Speaker Notes**: Demo this live. Type a query, show the colored entity chips. Emphasize the 3-step approach — the architecture makes hallucination very unlikely — rule-based parsing + real DB queries, the LLM only formats the results.

---

## SLIDE 12: Closing — Why DeskMind Wins

**Title**: Why DeskMind

**6 differentiators (numbered, large text):**

1. **94.1% accuracy** — benchmark-verified, not a claim
2. **Agentic AI** — classifies, generates resolutions, predicts incidents, enriches tickets
3. **Self-learning** — 3 feedback loops, gets smarter with every ticket
4. **Knowledge graph** — real infrastructure relationships powering decisions
5. **Hallucination-resistant** — every AI response grounded in real data
6. **100% on-premise** — no cloud APIs, full data privacy, works offline

**Bottom (large)**: 24 backend services | 26 frontend components | 32 API endpoints | 10 AI features | 40 documentation files

**Final line**: "DeskMind — Intelligent IT Ticket Routing That Actually Solves Problems"

**Speaker Notes**: End strong. These 6 points are your closing argument. Pause after each one. Then: "Thank you. We're happy to take questions."

---

## BONUS: Q&A Cheat Sheet (not a slide — for your reference)

| Question | Key Answer |
|----------|-----------|
| How handle misclassification? | Override → correction tracked → cache flushed → centroids retrained |
| What if LLM goes down? | Circuit breaker → Level 2 (3 classifiers, ~70% projected) → Level 1 (keyword, ~68% measured) |
| Why not GPT-4? | Data privacy + zero cost + no latency + works offline |
| How does graph help? | prod-db-01 → database server → DB Admin team → PostgreSQL → past fixes → experts |
| Can it scale? | Cache handles repeats (<10ms), Ollama supports concurrency, keyword fallback is instant |
| Real production accuracy? | 94.1% on 35 diverse tickets. Would need domain tuning for specific org. |
| How avoid hallucination in resolution? | Quality gate: only generates with reference data. System prompt constrains to sources. |
| Why 4 classifiers not just LLM? | Same accuracy but with resilience. LLM alone = single point of failure. |
| How does voting work? | 6 phases: unanimous → supermajority → pair → 2v2 with boundary override → disagreement |
| What would you change? | Start with 7B model from day 1, build eval benchmark earlier |
