# Architecture Diagrams

All diagrams use [Mermaid](https://mermaid.js.org/) syntax and render natively on GitHub.

---

## 1. System Container Diagram

```mermaid
graph TB
    User([User / Analyst])

    subgraph Frontend["Frontend (React + Vite)"]
        UI[Dashboard UI]
        Graph[Knowledge Graph Viz]
        Chat[Mindy AI Chat]
        Analytics[Analytics Dashboard]
    end

    subgraph Backend["Backend (FastAPI)"]
        API[REST API]
        WS[Socket.IO]
        Pipeline[Classification Pipeline]
        MW[Rate Limit Middleware]
        CB[Circuit Breaker]
    end

    subgraph Data["Data Layer"]
        Arango[(ArangoDB\nKnowledge Graph\nVector Search)]
        Redis[(Redis\nCache + SLA\nRate Limiting)]
        Ollama[Ollama\nQwen 2.5:7B\nLocal LLM]
    end

    User --> UI
    UI --> API
    UI --> WS
    API --> MW --> Pipeline
    Pipeline --> CB --> Ollama
    Pipeline --> Arango
    Pipeline --> Redis
    WS --> UI

    style Frontend fill:#1e293b,stroke:#F97316,color:#f5f5f4
    style Backend fill:#1e293b,stroke:#3b82f6,color:#f5f5f4
    style Data fill:#1e293b,stroke:#22c55e,color:#f5f5f4
```

---

## 2. Data Flow Diagram (7 Steps)

```mermaid
flowchart LR
    A[1. User submits ticket] --> B[2. PII masking\n+ entity extraction]
    B --> C[3. Generate embedding\nMiniLM 384-dim]
    C --> D[4. Cache check\nTier A → Tier B]
    D -->|Hit| G[7. Route to team]
    D -->|Miss| E[5. 4 Classifiers\nin parallel]
    E --> F[6. Weighted voting\n+ confidence calibration]
    F -->|>= 70%| G
    F -->|< 70%| H[Escalate for\nhuman review]
    F -->|< 50% + Level 1| I[Pending human\nqueue]
    G --> J[Start SLA timer\nin Redis]

    style A fill:#F97316,color:#fff
    style G fill:#22c55e,color:#fff
    style H fill:#ef4444,color:#fff
    style I fill:#dc2626,color:#fff
```

---

## 3. AI Classification Pipeline

```mermaid
flowchart TD
    Input["Ticket: title + description"]

    subgraph Stage1["Stage 1: Prepare"]
        Entity[Entity Extraction\nspaCy + custom patterns]
        Quality[Quality Scoring\nHIGH / MEDIUM / LOW]
        Embed[Embedding\nMiniLM 384-dim]
    end

    subgraph Stage2["Stage 2: Retrieve"]
        Similar[Similar Tickets\ncosine search]
        ErrorMatch[Error Code\nmatching]
        GraphCtx[Graph Context\nteam → server → service]
        Fulltext[Fulltext Search]
    end

    subgraph Stage3["Stage 3: Classify (parallel)"]
        LLM["LLM Classifier\nQwen 2.5:7B\nWeight: 0.40"]
        Centroid["Centroid Classifier\nEmbedding distance\nWeight: 0.30"]
        KNN["KNN Classifier\nNearest neighbors\nWeight: 0.15"]
        Keyword["Keyword Classifier\nPattern matching\nWeight: 0.15"]
    end

    subgraph Stage4["Stage 4: Aggregate"]
        Vote[6-phase majority-aware voting]
        Calibrate[Confidence\n0.60*supporter_avg + 0.25*vote_share + 0.15*weight_share\nscenario + quality caps]
    end

    subgraph Stage5["Stage 5: Decide"]
        Route{Confidence >= 70%?}
        Routed[Auto-Route\nto team]
        Escalated[Escalate\nfor review]
    end

    Input --> Stage1
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Vote
    Vote --> Calibrate
    Calibrate --> Route
    Route -->|Yes| Routed
    Route -->|No| Escalated
```

---

## 4. Knowledge Graph Schema

```mermaid
graph LR
    Teams((Teams\n6 nodes))
    Engineers((Engineers\n12 nodes))
    Servers((Servers\n15 nodes))
    Services((Services\n12 nodes))
    Tickets((Tickets\n~900 nodes))
    ErrorCodes((Error Codes\n20 nodes))
    NetDevices((Network\nDevices\n5 nodes))

    Engineers -->|member_of| Teams
    Servers -->|managed_by| Teams
    Services -->|depends_on| Servers
    Tickets -->|assigned_to| Teams
    Tickets -->|affects| Servers
    Tickets -->|triggered_by| ErrorCodes
    Tickets -->|resolved_with| Resolutions((Resolutions))
    NetDevices -->|managed_by| Teams

    style Teams fill:#3b82f6,color:#fff
    style Engineers fill:#22c55e,color:#fff
    style Servers fill:#F97316,color:#fff
    style Services fill:#8b5cf6,color:#fff
    style Tickets fill:#f59e0b,color:#fff
    style ErrorCodes fill:#ef4444,color:#fff
    style NetDevices fill:#06b6d4,color:#fff
    style Resolutions fill:#22c55e,color:#fff
```

**Node types:** 7 | **Edge types:** 8 | **Total nodes:** ~975 (live DB, 2026-06-11; illustrative)

---

## 5. Multi-Signal Confidence Flow

```mermaid
flowchart TD
    LLM["LLM Vote\n0.40 weight"] --> Agg
    Centroid["Centroid Vote\n0.30 weight"] --> Agg
    KNN["KNN Vote\n0.15 weight"] --> Agg
    Keyword["Keyword Vote\n0.15 weight"] --> Agg

    Agg["6-phase majority-aware vote\nwinner = (votes desc, weighted desc, name asc)"] --> Base["Base Confidence\n0.60*supporter_avg + 0.25*vote_share + 0.15*weight_share\n+0.03 if error codes confirm, +0.02 if graph confirms"]

    Base --> Phase{"Winning\nphase / scenario?"}

    Phase -->|"unanimous (4/4)"| ScUnan["scenario cap 0.95"]
    Phase -->|"supermajority (3+ agree)"| ScSuper["scenario cap 0.85 / 0.65"]
    Phase -->|"pair beats singles (2/1/1)"| ScPair["scenario cap 0.70"]
    Phase -->|"2v2 DB/Infra boundary"| ScBoundary["dissenter_override 0.60 / weighted_2v2 0.65"]
    Phase -->|"total disagreement"| ScDisagree["scenario cap 0.50"]

    ScUnan --> QualityCap
    ScSuper --> QualityCap
    ScPair --> QualityCap
    ScBoundary --> QualityCap
    ScDisagree --> QualityCap

    QualityCap{"Quality\nScore?"}
    QualityCap -->|HIGH| Cap99["Cap: 0.99"]
    QualityCap -->|MEDIUM| Cap85["Cap: 0.85"]
    QualityCap -->|LOW| Cap69["Cap: 0.69"]

    Cap99 --> Final["Final Confidence\nmin(base + bonus, scenario cap, quality cap)"]
    Cap85 --> Final
    Cap69 --> Final

    Final --> Decision{">= 0.70?"}
    Decision -->|Yes| Route["Auto-Route"]
    Decision -->|No| Escalate["Escalate"]

    style Route fill:#22c55e,color:#fff
    style Escalate fill:#ef4444,color:#fff
```

---

## 6. Graceful Degradation Levels

```mermaid
stateDiagram-v2
    [*] --> Level4: All systems UP

    Level4: Level 4 — Full Pipeline
    Level4: LLM(0.40) + Centroid(0.30) + KNN(0.15) + Keyword(0.15)

    Level3: Level 3 — No Data
    Level3: LLM(0.80) + Keyword(0.20)

    Level2: Level 2 — No LLM
    Level2: Centroid(0.50) + KNN(0.25) + Keyword(0.25)

    Level1: Level 1 — Emergency
    Level1: Keyword(1.00)

    Level4 --> Level3: DB empty
    Level4 --> Level2: Ollama down
    Level3 --> Level1: Ollama also down
    Level2 --> Level1: DB also empty

    Level3 --> Level4: DB populated
    Level2 --> Level4: Ollama recovered
    Level1 --> Level2: DB recovered
    Level1 --> Level3: Ollama recovered
```
