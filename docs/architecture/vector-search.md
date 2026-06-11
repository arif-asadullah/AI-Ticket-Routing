# Vector Search — Finding Similar Tickets by Meaning

## What Problem Does This Solve?

When a new ticket comes in — "PostgreSQL not accepting connections" — we want to find past tickets about the **same type of problem**. Not just tickets with the same words, but tickets with the **same meaning**.

Why not just search by keywords? Because:
- "PostgreSQL not accepting connections" and "Database refusing new connections" mean the **same thing** but share **zero keywords** (other than "connections")
- "Redis connection pool exhausted" is a **similar problem** (connection issue on a database) even though it uses completely different words
- Keyword search would miss these — vector search finds them

## Real-World Analogy

Imagine you walk into a library and say "I need a book about growing tomatoes."

- **Keyword search** = the librarian searches the catalog for the word "tomatoes". Misses books titled "Home Vegetable Gardening" (no word "tomatoes" in the title).
- **Vector search** = the librarian **understands what you mean** and brings you all books about vegetable gardening, even if they don't mention "tomatoes" specifically.

Vector search understands **meaning**, not just words.

## How It Works — Step by Step

### Step 1: Convert Text to Numbers (Embedding)

The MiniLM model reads the ticket description and converts it into a list of **384 numbers**. This list is called an **embedding** or **vector**.

```
Input:  "PostgreSQL not accepting connections on prod-db-01"
            ↓
        MiniLM model processes the text
            ↓
Output: [0.82, -0.15, 0.33, 0.07, -0.44, 0.21, ... 378 more numbers]
```

These 384 numbers represent the **meaning** of the sentence in "meaning space" — like GPS coordinates, but instead of latitude/longitude (2 numbers), it uses 384 dimensions to capture every nuance of meaning.

### Step 2: Every Past Ticket Already Has an Embedding

When tickets are loaded into the database, their descriptions are also converted to embeddings:

```
Ticket TKT-042: "PostgreSQL max_connections reached"
  → embedding: [0.80, -0.14, 0.35, 0.09, -0.42, 0.19, ...]

Ticket TKT-056: "Slow queries blocking production traffic"
  → embedding: [0.45, -0.08, 0.61, 0.33, -0.15, 0.52, ...]

Ticket TKT-089: "NGINX returning 502 Bad Gateway"
  → embedding: [0.11, 0.67, -0.22, 0.44, 0.28, -0.38, ...]
```

### Step 3: Compare the New Embedding to All Past Embeddings

The system calculates **how similar** the new ticket's embedding is to every past ticket's embedding. This similarity is measured using **cosine similarity** — a number between 0 and 1:

- **1.0** = identical meaning
- **0.8+** = very similar
- **0.5** = somewhat related
- **0.0** = completely unrelated

```
New ticket embedding:  [0.82, -0.15, 0.33, ...]

Compare to:
  TKT-042 [0.80, -0.14, 0.35, ...] → similarity: 0.96  ← VERY SIMILAR!
  TKT-056 [0.45, -0.08, 0.61, ...] → similarity: 0.72  ← somewhat related
  TKT-089 [0.11, 0.67, -0.22, ...] → similarity: 0.23  ← not related (NGINX, not DB)
```

### Step 4: Return the Top 5 Most Similar

```
Results (sorted by similarity):
  1. TKT-042 "PostgreSQL max_connections reached"     — 0.96
  2. TKT-078 "Database connection pool exhausted"      — 0.89
  3. TKT-056 "Slow queries blocking production"        — 0.72
  4. TKT-033 "Redis OOM on prod-app-01"                — 0.65
  5. TKT-012 "prod-db-01 disk space critical"          — 0.58
```

Notice: TKT-042 uses different words ("max_connections reached" vs "not accepting connections") but the meaning is almost identical (0.96 similarity).

## What Happens with These 5 Results?

Each similar ticket is linked to its resolution via the `resolved_with` edge:

```
TKT-042 ──resolved_with──→ Resolution: "Killed idle connections, increased max_connections"
TKT-078 ──resolved_with──→ Resolution: "Increased connection pool size in app config"
```

For the primary source (similar past tickets), the suggestion is **similarity-gated**: a past resolution is used only if it is the **same category** AND `similarity >= 0.55` (`RES_SIM_THRESHOLD`), and the system takes the **first relevance-reranked match** — where the re-rank score is `0.60 * similarity + 0.20 * recency + 0.20 * effectiveness` (`retrieval.py` `_rerank`) — not simply the highest-effectiveness resolution. (Secondary sources — error-code matches and same-server tickets — still pick the highest `effectiveness`.)

## Which Database Fields Are Involved?

| Step | Collection | Field | Type | Purpose |
|------|-----------|-------|------|---------|
| 1 | `tickets` | `description` | string | The text that gets converted to embedding |
| 2 | `tickets` | `embedding` | array[384] | The 384 numbers representing the meaning |
| 3 | — | — | — | ArangoDB vector index does the comparison |
| 4 | `tickets` | `_key` | string | ID of the similar ticket found |
| 5 | `resolved_with` | `_from`, `_to` | edge | Links ticket to its resolution |
| 6 | `resolutions` | `steps` | array | The actual fix steps |
| 7 | `resolutions` | `effectiveness` | float | How well the fix worked (0.0 to 1.0) |

## The AQL Query

This is the actual database query that finds the 5 most similar tickets:

**Primary path** — the ANN vector index. Because the `APPROX_NEAR_COSINE` sort can't be combined with a pre-`FILTER` on status in the same loop, we over-fetch the nearest neighbors in a subquery, then filter status and recompute exact cosine on the survivors:

```aql
// @newEmbedding = the 384-number embedding of the new ticket
// @overfetch    = max(limit * 5, 25)   @limit = 5

FOR ticket IN (
    FOR t IN tickets
      SORT APPROX_NEAR_COSINE(t.embedding, @newEmbedding) DESC  // ANN vector index
      LIMIT @overfetch                              // over-fetch nearest neighbors
      RETURN t
  )
  FILTER ticket.status IN ["closed", "resolved"]    // only resolved tickets
  LIMIT @limit                                      // top 5 survivors
  LET sim = COSINE_SIMILARITY(ticket.embedding, @newEmbedding)  // exact, on survivors

  // For each similar ticket, get its resolution
  LET resolution = FIRST(
    FOR res IN 1..1 OUTBOUND ticket resolved_with
      RETURN res
  )

  RETURN {
    ticket_key: ticket._key,
    title: ticket.title,
    category: ticket.category,
    similarity: sim,
    resolution_steps: resolution.steps,
    effectiveness: resolution.effectiveness
  }
```

A brute-force `COSINE_SIMILARITY` full scan (single loop, no index) is used **only as a fallback** when the `APPROX_NEAR_COSINE` index path is unavailable.

## Why 384 Numbers? Why Not 2 or 10?

More numbers = more nuance captured. Think of it like describing a color:

- **1 number** = brightness only (is it light or dark?)
- **3 numbers** = RGB (red, green, blue — much more detail)
- **384 numbers** = captures meaning, tone, technical detail, urgency, which systems are involved, what type of error, and hundreds of other subtle aspects of the text

The MiniLM model was trained on millions of sentences to learn what these 384 dimensions should represent. We don't design them — the AI figured out the best way to encode meaning during training.

## What is Cosine Similarity?

Imagine two arrows pointing from the center of a circle. Cosine similarity measures **how much they point in the same direction**:

```
Same direction     → cosine = 1.0    (identical meaning)
      ↗
     ↗     ← small angle
    ↗

Slightly different → cosine = 0.85   (similar meaning)
      ↗
       ↗   ← medium angle
         →

Completely different → cosine = 0.0  (unrelated)
      ↑
      |    ← right angle (90°)
      ──→
```

The math is simple: multiply corresponding numbers, sum them up, divide by the lengths. But you don't need to understand the math — ArangoDB does it automatically with `APPROX_NEAR_COSINE`.

## Why is the Vector Index Important?

Without the vector index, ArangoDB would have to:
1. Load every ticket's 384-number embedding
2. Calculate cosine similarity with the new ticket
3. For 10,000 tickets = 10,000 calculations

With the vector index (ArangoDB faiss-based IVF index — dimension 384, metric cosine, `nLists` 10 — queried via `APPROX_NEAR_COSINE`), ArangoDB:
1. Uses a pre-built set of cluster "lists" grouping where similar embeddings are located
2. Jumps directly to the neighborhood (nearest lists) of similar tickets
3. Over-fetches the approximate nearest neighbors (5x the requested limit, minimum 25), then recomputes exact cosine similarity on the survivors
4. Returns results in **milliseconds** instead of seconds

If the index path is unavailable (e.g. on a fresh deploy where the vector index is not yet built), it falls back to an exact brute-force `COSINE_SIMILARITY` full scan.

## When Does Vector Search NOT Work Well?

| Situation | Why | What helps instead |
|-----------|-----|--------------------|
| Brand new system (no past tickets) | Nothing to compare against | LLM classifies from its own knowledge |
| Very short ticket ("server down") | Too little text → vague embedding | Error code matching, graph traversal |
| Ticket about a completely new issue type | No similar past ticket exists | LLM classifies from its own knowledge |

That's why DeskMind uses **4 methods** (vector similarity + error-code matching + graph traversal + full-text keyword search, per `retrieval.py` `retrieve_all()`), not just vector search alone.
