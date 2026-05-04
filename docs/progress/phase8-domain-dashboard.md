# Phase 8: Domain Dashboard & Full Ticket Lifecycle UI

## What We Did

Built a complete domain-specific dashboard where engineers can manage their team's tickets end-to-end — from viewing AI classification details to resolving tickets and giving feedback on AI suggestions. Also renamed the 6th domain from "Storage" to "Access Management" across the entire codebase.

## The Engineer Flow

```
Login → Dashboard (team-scoped tickets)
    → Click ticket → Full detail view
        → See AI classification, confidence, classifier votes
        → See suggested resolution + runbook + expert
        → Pick Up ticket (status → in_progress)
        → Resolve ticket (fill steps, rate AI suggestion, reference runbook)
        → Give feedback (👍/👎 on AI suggestion)
```

## What Was Built

### 1. Domain Dashboard (`DomainDashboard.jsx`)

The main page after login. Different view per role:

| Role | What They See |
|------|-------------|
| **Admin** | 6 domain cards (Infrastructure, Application, Database, Network, Security, Access Management) → click one → filtered ticket list |
| **Engineer** | Directly sees their team's tickets (e.g., Database Admin sees only Database tickets) |
| **User** | All tickets across all domains (read-only) |

Features:
- **Stats header**: Open, In Progress, Resolved counts
- **Filters**: Status dropdown, Priority dropdown, Search input
- **Ticket cards**: ID, title, priority badge, status badge, confidence bar, team, relative time
- **Inline create form**: Submit new tickets without leaving the dashboard

### 2. Ticket Detail (`TicketDetail.jsx`)

Full ticket view — opens when clicking a ticket card. Shows everything the AI did:

- **Ticket info**: Title, full description, submitted by, timestamps
- **AI Classification card**: Category badge, confidence bar (green/yellow/red), quality score
- **Classifier Votes**: 4 mini-cards showing LLM, KNN, Centroid, Keyword — each with category + confidence. Votes agreeing with the final category highlighted in green.
- **AI Reasoning**: The LLM's explanation in a callout box
- **Suggested Resolution**: Numbered steps from similar past tickets, effectiveness percentage
- **Recommended Runbook**: KB number + title
- **Recommended Expert**: Name from knowledge graph
- **Action buttons** (based on status):
  - Routed → "Pick Up" + "Escalate"
  - In Progress → "Resolve" + "Escalate"
  - Resolved → "Reopen" + Feedback widget
  - Escalated → "Pick Up"

### 3. Resolve Form (`ResolveForm.jsx`)

Modal for resolving a ticket:

- **AI suggestion reference**: Shows the AI's suggested resolution at the top (if available) with effectiveness %
- **Resolution steps**: Dynamic list — add/remove steps. Pre-filled from AI suggestion if available.
- **"Did the AI suggestion help?"**: Three toggle buttons — Yes / Partially / No
- **Runbook used**: Text input, pre-filled from suggested runbook
- Submit → creates resolution document + edges in knowledge graph

### 4. Feedback Widget (`FeedbackWidget.jsx`)

Inline rating after resolution:

- 👍 Helpful / 👎 Not Helpful buttons
- Optional comment textarea
- Stores feedback in audit_log collection
- "Thanks for your feedback!" confirmation after submit

### 5. Feedback API

**Endpoint**: `POST /api/tickets/{id}/feedback`

```python
class TicketFeedback(BaseModel):
    rating: str       # "helpful" or "not_helpful"
    comment: str | None = None
```

Stores in `audit_log` with action "feedback", the user's email as actor, and the rating/comment.

### 6. Storage → Access Management Rename

Replaced the 6th domain across the entire codebase:

| Layer | Files Changed |
|-------|--------------|
| Seed data | Team, engineers, error codes, runbook, 9 tickets, 5 resolutions, routing rules, centroid, edges |
| Synthetic data | Deleted 94 Storage tickets, generated 94 Access Management tickets (GPT-4o + Claude + Noise) |
| Backend code | keyword_classifier.py, error_scanner.py, llm_classifier.py |
| Scripts | generate_tickets.py, generate_noise_tickets.py, generate_claude_tickets*.py |
| Documentation | 15 docs updated (architecture, schema, progress, nasscom-r2) |

### 7. Classifiers Explained Doc

New documentation: `docs/architecture/classifiers-explained.md` — 536 lines explaining how all 4 classifiers work with math formulas, worked examples, and comparison tables.

## File Summary

| File | What |
|------|------|
| `frontend/src/components/DomainDashboard.jsx` | Domain selector + filtered ticket cards + inline create + stats |
| `frontend/src/components/TicketDetail.jsx` | Full ticket view with AI data + action buttons |
| `frontend/src/components/ResolveForm.jsx` | Resolution modal with dynamic steps + AI feedback |
| `frontend/src/components/FeedbackWidget.jsx` | Thumbs up/down rating widget |
| `frontend/src/services/api.js` | Added fetchTicket, updateTicketStatus, resolveTicket, submitFeedback |
| `frontend/src/App.jsx` | Dashboard tab (default), domain routing, user guard |
| `backend/api/tickets.py` | POST /api/tickets/{id}/feedback endpoint |
| `backend/schemas/ticket.py` | TicketFeedback model |
| `backend/services/keyword_classifier.py` | Access Management keywords (was Storage) |
| `backend/services/error_scanner.py` | active-directory → Access Management mapping |
| `backend/services/llm_classifier.py` | Updated prompt + valid_cats for Access Management |
| `docs/architecture/classifiers-explained.md` | KNN, Centroid, Keyword, Aggregator deep dive |
