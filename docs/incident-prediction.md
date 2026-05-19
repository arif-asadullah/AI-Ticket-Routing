# Proactive Incident Prediction

> DeskMind doesn't just classify individual tickets — it scans for patterns across all recent tickets and warns teams about emerging incidents BEFORE they escalate.

---

## How It Works

```
Every 60 seconds, DeskMind scans recent tickets:
        |
        v
Cluster Detection: 3+ tickets routed to same team in 4 hours?
        |           "8 Infrastructure tickets in 4h → possible outage"
        v
Trend Detection: Category volume 50%+ higher than last week?
        |           "Network tickets up 150% this week"
        v
Spike Detection: 5+ new tickets in the last hour?
        |           "20 tickets in 1 hour → unusual volume"
        v
Pulsing red banner on dashboard with AI-generated alerts
```

---

## What Gets Detected

### 1. Cluster Patterns (CRITICAL / HIGH)

When 3 or more tickets are routed to the same team within a 4-hour window, DeskMind flags it as a potential outage.

**Example alert:**
> **CRITICAL | CLUSTER**
> Possible outage: 8 Infrastructure tickets in 4 hours
> All routed to Infrastructure Ops
> *Suggested: Check Infrastructure systems, contact Infrastructure Ops*

**Severity thresholds:**
- 5+ tickets in 4h → CRITICAL
- 4 tickets in 4h → HIGH
- 3 tickets in 4h → WARNING

### 2. Category Trends (WARNING)

When a category's ticket volume this week is 50%+ higher than last week (and at least 3 tickets), DeskMind flags it as a trend.

**Example alert:**
> **WARNING | TREND**
> Network tickets trending up: 5 this week vs 2 last week
> 150% increase from last week
> *Suggested: Review recent Network changes and deployments*

### 3. Volume Spikes (CRITICAL)

When 5 or more new tickets arrive within a single hour, DeskMind flags it as an unusual volume spike.

**Example alert:**
> **CRITICAL | SPIKE**
> Ticket spike: 20 new tickets in the last hour
> Unusual volume detected
> *Suggested: Check for widespread outage or incident*

---

## Role-Based Filtering

Not everyone needs to see every alert.

| Role | What They See |
|------|--------------|
| **Admin** | ALL incidents across all teams and categories |
| **Engineer** (e.g., Database Admin) | Only incidents for their team + general spikes |
| **Regular User** | Only general spike alerts |

**Example:** An engineer on the Database Admin team only sees:
- "4 Database tickets in 4 hours" ← their team
- "20 tickets in the last hour" ← general spike
- Does NOT see: "8 Infrastructure tickets in 4 hours" ← not their team

---

## Domain-Filtered View

When an admin clicks into a specific domain (e.g., Infrastructure), the incident banner filters to show only incidents relevant to that domain.

- **All Tickets view** → all incidents
- **Infrastructure view** → only Infrastructure clusters + general spikes
- **Database view** → only Database clusters + general spikes

---

## Dashboard Banner

The incident predictions appear as a pulsing red/orange banner between the stats bar and the ticket list.

```
┌─────────────────────────────────────────────────────────────┐
│ ● AI Predicted Incidents (3)                                │
│   DeskMind detected unusual patterns in recent tickets —    │
│   these are not tickets, they are AI-generated alerts       │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ CRITICAL  CLUSTER                                       │ │
│ │ Possible outage: 8 Infrastructure tickets in 4 hours    │ │
│ │ All routed to Infrastructure Ops                        │ │
│ │ Suggested: Check Infrastructure systems                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ CRITICAL  SPIKE                                         │ │
│ │ Ticket spike: 20 new tickets in the last hour           │ │
│ │ Unusual volume detected                                 │ │
│ │ Suggested: Check for widespread outage or incident      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ WARNING  TREND                                          │ │
│ │ Network tickets trending up: 5 this week vs 2 last week │ │
│ │ 150% increase from last week                            │ │
│ │ Suggested: Review recent Network changes                │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

The banner:
- Has a pulsing red dot to draw attention
- Clearly states "these are not tickets, they are AI-generated alerts"
- Shows severity badge (CRITICAL / HIGH / WARNING) and type (CLUSTER / TREND / SPIKE)
- Includes suggested actions for each incident
- Auto-refreshes every 60 seconds
- Disappears when no patterns are detected

---

## API

### Get Active Incidents

```
GET /api/incidents
Authorization: Bearer <token>
```

Response:
```json
[
    {
        "type": "cluster",
        "severity": "critical",
        "title": "Possible outage: 8 Infrastructure tickets in 4 hours",
        "details": "All routed to Infrastructure Ops",
        "suggested_action": "Check Infrastructure systems, contact Infrastructure Ops",
        "count": 8,
        "category": "Infrastructure",
        "team": "Infrastructure Ops"
    },
    {
        "type": "spike",
        "severity": "critical",
        "title": "Ticket spike: 20 new tickets in the last hour",
        "details": "Unusual volume detected",
        "suggested_action": "Check for widespread outage or incident",
        "count": 20
    },
    {
        "type": "trend",
        "severity": "warning",
        "title": "Network tickets trending up: 5 this week vs 2 last week",
        "details": "150% increase from last week",
        "suggested_action": "Review recent Network changes and deployments",
        "count": 5,
        "category": "Network"
    }
]
```

---

## Caching

Results are cached in Redis for 60 seconds per user role + team combination:
- Key: `incidents:predictions:{role}:{team_key}`
- TTL: 60 seconds
- First request: runs full scan (~50ms)
- Subsequent requests within 60s: returns cached result (<1ms)

This keeps the dashboard responsive while providing near-real-time alerting.

---

## Why This Matters

Without incident prediction:
1. User submits ticket → classified → routed to team
2. Another user submits similar ticket → classified → routed
3. Three more similar tickets arrive → each handled individually
4. Team lead finally notices: "Wait, we have 8 Infrastructure tickets in 4 hours — is there an outage?"
5. 4 hours wasted before anyone connected the dots

With incident prediction:
1. Third similar ticket arrives → DeskMind detects the pattern
2. Pulsing red banner: "Possible outage: 3 Infrastructure tickets in 4 hours"
3. Team lead sees it immediately → investigates → finds root cause
4. Issue resolved before more tickets come in

The AI proactively monitors and warns. Nobody asked it to — it does it autonomously. This is agentic AI.

---

## Technical Details

- **Cluster scan:** AQL query groups open tickets by team + category in the last 4 hours
- **Trend scan:** Compares this week's category volumes to last week's using date-based AQL aggregation
- **Spike scan:** Counts all new user tickets in the last hour
- **Sorting:** Results sorted by severity (critical → high → warning)
- **Filtering:** Applied after scan based on user's role and team_key from JWT token
