# Indexes

This document explains what indexes are, why they matter, and which ones DeskMind uses.

## What is an index?

Imagine you have a phonebook with 10,000 names. To find "Alex Chen":
- **Without an index**: Read every name from page 1 until you find Alex Chen. Slow.
- **With an index**: The phonebook is sorted alphabetically. Jump to "C", find "Chen". Fast.

A database index works the same way. It creates a shortcut so the database can find data without scanning every document.

## Why indexes matter

| Without index | With index |
|--------------|-----------|
| "Find all high priority tickets" → scan all 10,000 tickets | Jump directly to high priority tickets → milliseconds |
| "Search for PostgreSQL" in descriptions → read every description | Full-text index → instant match |
| "Find tickets similar to this one" → compute distance to all embeddings | Vector index → fast approximate match |

**Rule of thumb**: If you frequently filter or search by a field, create an index on it.

---

## Index Types in DeskMind

### 1. Persistent Index

**What it is**: A sorted list of values for a field. Like sorting a spreadsheet column.

**When to use**: When you filter by exact values — "show me all tickets where category = Database."

#### Indexes we create:

**On `tickets` collection:**

| Fields | Why | Example query |
|--------|-----|---------------|
| `category` | Filter tickets by domain | `FOR t IN tickets FILTER t.category == "Database" RETURN t` |
| `priority` | Filter by urgency | `FOR t IN tickets FILTER t.priority == "critical" RETURN t` |
| `status` | Filter by lifecycle state | `FOR t IN tickets FILTER t.status == "open" RETURN t` |
| `created_at` | Sort by newest first | `FOR t IN tickets SORT t.created_at DESC LIMIT 20 RETURN t` |

**On `routing_rules` collection:**

| Fields | Why | Example query |
|--------|-----|---------------|
| `category` + `priority` | Fast rule lookup | `FOR r IN routing_rules FILTER r.category == "Database" AND r.priority == "high" RETURN r` |

**On `users` collection:**

| Fields | Why | Example query |
|--------|-----|---------------|
| `email` (unique) | Fast login lookup + prevent duplicate accounts | `FOR u IN users FILTER u.email == "arif@company.com" RETURN u` |

This is a **unique** persistent index — ArangoDB rejects any insert that would create a duplicate email.

**Without these indexes**: Every query scans the entire collection. With 50 tickets it's fine. With 10,000 tickets it becomes slow. Indexes keep it fast regardless of collection size.

---

### 2. Full-Text Index

**What it is**: A special index that lets you search for words or phrases inside text fields — like a Google search within your database.

**When to use**: When users need to search ticket text by keywords.

#### Index we create:

**On `tickets` collection:**

| Fields | Why | Example query |
|--------|-----|---------------|
| `title`, `description` | Keyword search across tickets | Find all tickets mentioning "PostgreSQL" or "connection refused" |

**How it works**:

```
AQL:
FOR t IN FULLTEXT(tickets, "description", "PostgreSQL connection")
  RETURN t
```

This finds all tickets where the description contains "PostgreSQL" AND "connection" — even if the words aren't next to each other.

**Without full-text index**: You'd have to use `LIKE "%PostgreSQL%"` which is much slower and doesn't support relevance ranking.

---

### 3. Vector Index (the most important one for AI)

**What it is**: A special index that lets you find documents with **similar meaning**, not just matching keywords.

**When to use**: When you want to find "tickets similar to this one" based on what they mean, not just what words they use.

#### How it works (simplified):

1. When a ticket is created, the MiniLM model converts its description into a list of 384 numbers (called an "embedding" or "vector").
2. These numbers represent the **meaning** of the text.
3. Two texts with similar meanings have similar numbers.
4. The vector index organizes these numbers so similar ones are close together.
5. When you search, it quickly finds the nearest neighbors.

#### Example:

```
Ticket A: "PostgreSQL not accepting connections"
   Embedding: [0.82, -0.15, 0.33, ...]

Ticket B: "Database refusing new connections"
   Embedding: [0.80, -0.14, 0.35, ...]  ← very similar numbers!

Ticket C: "NGINX returning 502 errors"
   Embedding: [0.11, 0.67, -0.22, ...]  ← very different numbers
```

Searching for tickets similar to A returns B first (similar meaning), not C (different meaning) — even though B uses completely different words.

#### Indexes we create:

| Collection | Field | Dimensions | Why |
|-----------|-------|-----------|-----|
| `tickets` | `embedding` | 384 | Find similar past tickets to help classify and route new ones |
| `runbooks` | `embedding` | 384 | Find the most relevant runbook for a new ticket |
| `resolutions` | `embedding` | 384 | Find similar past fixes to suggest for new tickets |

#### Example query:

```
AQL:
FOR t IN tickets
  SORT APPROX_NEAR_COSINE(t.embedding, @queryEmbedding)
  LIMIT 5
  RETURN t
```

This finds the 5 tickets most similar in meaning to the query embedding. The vector index makes this fast — without it, ArangoDB would have to compute the distance to every single ticket.

#### Technical details:
- **384 dimensions**: The MiniLM model (all-MiniLM-L6-v2) produces 384-dimensional vectors. Each dimension captures one aspect of meaning.
- **Cosine similarity**: We measure similarity by the angle between two vectors. 1.0 = identical meaning, 0.0 = completely unrelated.
- **faiss-based IVF index**: ArangoDB builds a faiss-based IVF (inverted file) vector index — dimension 384, metric cosine, nLists 10 — queried via `APPROX_NEAR_COSINE` for fast approximate nearest neighbor search. If the index is unavailable, the query falls back to an exact brute-force `COSINE_SIMILARITY` scan. Don't worry about the name — just know it makes similarity search fast.
- **Approximate**: The index trades a tiny bit of accuracy for a lot of speed. To compensate, the ANN query over-fetches candidates (5× the requested limit, minimum 25) and recomputes exact cosine similarity on the survivors so the returned top matches are accurate.

---

## Summary of all indexes

| # | Collection | Type | Fields | Purpose |
|---|-----------|------|--------|---------|
| 1 | tickets | Persistent | `category` | Filter by domain |
| 2 | tickets | Persistent | `priority` | Filter by urgency |
| 3 | tickets | Persistent | `status` | Filter by lifecycle |
| 4 | tickets | Persistent | `created_at` | Sort by date |
| 5 | tickets | Full-text | `title` | Keyword search on titles |
| 6 | tickets | Full-text | `description` | Keyword search on descriptions |
| 7 | tickets | Vector (384) | `embedding` | Find similar tickets |
| 8 | runbooks | Vector (384) | `embedding` | Find relevant runbooks |
| 9 | resolutions | Vector (384) | `embedding` | Find similar fixes |
| 10 | routing_rules | Persistent | `category`, `priority` | Fast rule lookup |
| 11 | audit_log | Persistent | `ticket_id` | Find all actions for a ticket |
| 12 | audit_log | Persistent | `created_at` | Time-ordered audit trail |
| 13 | users | Persistent (unique) | `email` | Fast login lookup, prevent duplicates |

## When are indexes created?

Indexes are created automatically when the backend starts (in `backend/services/schema.py`). After that, ArangoDB maintains them — every time you insert, update, or delete a document, the index updates itself. You don't need to do anything.
