# Phase 5: Frontend & UI/UX

## What We Did

Built the DeskMind frontend with a futuristic dark theme, animated landing page, ticket submission, chat AI, and DeskMind branding.

## The User Journey

```
1. App loads → Splash screen (animated DeskMind logo, 3 seconds)
2. Landing page → "Raise Ticket" button
3. Dashboard → Submit ticket form + ticket list + Chat AI tab
```

## What Was Built

### 1. DeskMind Branding

**Logo system** (stored in `frontend/src/assets/logo/`):
- `deskmind-icon.svg` — square icon for favicon/small spaces
- `deskmind-logo.svg` — stacked logo (icon + "DeskMind" + tagline)
- `deskmind-logo-dark.svg` — for dark backgrounds
- `deskmind-logo-landscape.svg` — horizontal layout
- `deskmind-logo-landscape-dark.svg` — horizontal for dark header

**Browser tab**: DeskMind icon as favicon, title "DeskMind"

**Brand colors**: Orange (#F97316) as accent on dark (#0C0C0F) background.

### 2. Splash Screen

**File**: `frontend/src/components/DeskMindSplash.jsx`

Animated tree growing with branching nodes — symbolizes ticket routing (one input → multiple teams). Shows "DeskMind" wordmark and "CLASSIFY · ROUTE · RESOLVE" tagline. Auto-dismisses after 3.2 seconds.

### 3. Landing Page

**File**: `frontend/src/components/LandingPage.jsx`

Dark page with:
- **Animated background** (`AnimatedBackground.jsx`) — floating graph nodes with connecting lines (canvas animation). Represents the knowledge graph.
- **Hero section** — large DeskMind logo with glow effect, tagline "AI-powered ticket routing that learns your infrastructure"
- **"Raise Ticket" button** — glowing orange CTA
- **Status pills** — live indicators showing ArangoDB Connected, Redis Connected, Qwen 2.5 LLM Ready
- **"How It Works"** — 3 glass-morphism cards: Submit → Classify → Route
- **Live stats bar** — ticket count, team count, service count
- **Footer CTA** — "Ready to route smarter?"

### 4. Neural Dark Theme

All UI components use a dark theme:

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0C0C0F` | Near-black page background |
| Card | `rgba(255,255,255,0.04)` | Glass-morphism surfaces |
| Border | `rgba(255,255,255,0.08)` | Subtle card borders |
| Accent | `#F97316` | Orange — buttons, active states |
| Text | `#F5F5F4` | Primary text (warm white) |
| Text muted | `#78716C` | Secondary text |

**Typography**: Inter (headings), JetBrains Mono (data/IDs), system-ui (body).

### 5. Ticket Form + List

**Files**:
- `frontend/src/App.jsx` — main app with tab navigation (Tickets / Chat AI)
- `frontend/src/components/TicketList.jsx` — table with grid layout
- `frontend/src/components/StatusBar.jsx` — ArangoDB/Redis status in header

**Ticket form features**:
- Title input + description textarea with orange focus glow
- Priority selector (Low / Medium / High — segmented buttons)
- Submit button with DeskMindSpinner during classification
- 1.5 second minimum spinner (so user sees processing feedback)

**Ticket list features**:
- Grid table: ID, Title, Routed To, Priority, Status, Delete
- Priority badges with colored dots (red/amber/green)
- Status badges with green dots
- Hover highlights (orange tint)
- Trash icon delete button
- Empty state with illustration

**After submission**: Shows result card with:
- Routed team name
- Ticket status (routed/escalated)
- Priority badge

### 6. Chat AI Panel

**File**: `frontend/src/components/ChatPanel.jsx`

A direct chat interface with Qwen 2.5:3B via Ollama. Allows users to test the LLM interactively.

Features:
- Message bubbles (orange for user, dark glass for AI)
- DeskMindSpinner while AI is thinking
- Model name shown under each AI response
- Chat history maintained for context
- Input with orange focus ring

**Backend**: `POST /api/chat` → `backend/api/chat.py` → `backend/services/llm.py` → Ollama

### 7. DeskMind Spinner

**File**: `frontend/src/components/DeskMindSpinner.jsx`

Animated loading indicator matching the DeskMind logo — branching tree nodes pulsing. Available in 3 sizes: sm (button), md (card), lg (full page).

## File Summary

| File | What |
|------|------|
| `frontend/src/App.jsx` | Main app — tabs, ticket form, classifier integration |
| `frontend/src/components/LandingPage.jsx` | Landing page with hero + how it works |
| `frontend/src/components/AnimatedBackground.jsx` | Floating graph nodes canvas |
| `frontend/src/components/DeskMindSplash.jsx` | Animated splash screen |
| `frontend/src/components/DeskMindSpinner.jsx` | Loading spinner (3 sizes) |
| `frontend/src/components/StatusBar.jsx` | ArangoDB/Redis status dots |
| `frontend/src/components/TicketList.jsx` | Ticket table with dark theme |
| `frontend/src/components/ChatPanel.jsx` | Chat with Ollama |
| `frontend/src/services/api.js` | API client (fetchTickets, createTicket, sendChat, etc.) |
| `frontend/src/assets/logo/` | 5 SVG logo variants |
| `frontend/index.html` | Entry point with Inter + JetBrains Mono fonts |
| `frontend/vite.config.js` | Dev server + API proxy to backend |
