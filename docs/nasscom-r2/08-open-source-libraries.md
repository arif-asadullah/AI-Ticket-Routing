# DeskMind — Open Source & Libraries

> **Nasscom AI-Code-Sarathi Excel Hackathon — Final Round (Jury)**

---

## 1. Open Source Technologies

### Core Infrastructure

| Technology | Version | License | Role in DeskMind |
|-----------|---------|---------|-----------------|
| **ArangoDB** | 3.12 Community | Apache 2.0 | Multi-model database — graph engine + document store + vector search in one. Stores the entire knowledge graph (~1,800 documents, ~3,500 edges, generated at seed time). Provides native vector similarity search for semantic ticket matching. |
| **Redis** | 7.x | BSD 3-Clause | In-memory cache for health check results (5s TTL), entity lists (5min TTL), and performance optimization. |
| **Ollama** | Latest | MIT | Local LLM runtime. Hosts Qwen 2.5:7B model with OpenAI-compatible API. Enables fully local inference with no cloud dependency. |
| **Docker** | Latest | Apache 2.0 | Container runtime for all services. Ensures consistent environments across Mac and Windows development machines. |
| **Docker Compose** | Latest | Apache 2.0 | Multi-container orchestration. Single `docker compose up` starts the entire stack. |

### AI / ML Models

| Model | Parameters | License | Role in DeskMind |
|-------|-----------|---------|-----------------|
| **Qwen 2.5:7B** | 7 billion | Apache 2.0 | Primary LLM classifier (weight: 0.40, accuracy: 94.1%). Reads ticket text + retrieved context and classifies by root cause. Also powers the AI Resolution Generator and Chat AI interface. Upgraded from 3B for better reasoning. |
| **all-MiniLM-L6-v2** | 22 million | Apache 2.0 | Sentence embedding model. Converts ticket text to 384-dimensional vectors for semantic similarity search, KNN classification, and centroid distance classification. |

---

## 2. Backend Libraries (Python)

| Library | Version | License | Purpose |
|---------|---------|---------|---------|
| **FastAPI** | Latest | MIT | Async web framework. Provides REST API endpoints with automatic OpenAPI documentation, request validation, and dependency injection. |
| **Uvicorn** | Latest | BSD 3-Clause | ASGI server. Runs FastAPI with async support for concurrent request handling. |
| **sentence-transformers** | Latest | Apache 2.0 | Loads and runs the MiniLM embedding model. Provides `SentenceTransformer.encode()` for converting text to 384-dim vectors. |
| **python-arango** | Latest | MIT | ArangoDB Python driver. Handles document CRUD, AQL query execution, graph traversal, and collection management. |
| **redis** (aioredis) | Latest | MIT | Async Redis client. Used for caching health checks and entity lists with TTL-based expiration. |
| **httpx** | Latest | BSD 3-Clause | Async HTTP client. Makes API calls to Ollama's OpenAI-compatible endpoint for LLM classification and chat. |
| **Pydantic** | v2 | MIT | Data validation and serialization. Defines request/response schemas (TicketCreate, TicketResponse, etc.) with automatic type checking. |
| **pydantic-settings** | Latest | MIT | Configuration management. Loads settings from `.env` file with type validation and defaults. |
| **spaCy** | Latest | MIT | NLP library for text processing. Used in entity extraction and text normalization pipeline. |
| **python-jose** | Latest | MIT | JWT token creation, signing, and validation. Creates access tokens (30 min) and refresh tokens (7 days) for authentication. Uses HS256 algorithm. |
| **bcrypt** | 4.1.3 | Apache 2.0 | Password hashing. Direct bcrypt calls for hashing and verifying user passwords. |
| **pytesseract** | Latest | Apache 2.0 | OCR engine wrapper for Tesseract. Extracts text from uploaded screenshots for classification. |
| **python-multipart** | Latest | MIT | Multipart form data parsing for file upload endpoint (required by FastAPI for file handling). |
| **python-socketio** | Latest | MIT | Socket.IO server for real-time ticket update events (ticket:created, ticket:updated). |
| **python-dotenv** | Latest | BSD 3-Clause | Loads environment variables from `.env` file at application startup. |

---

## 3. Frontend Libraries (JavaScript)

| Library | Version | License | Purpose |
|---------|---------|---------|---------|
| **React** | 19.1.0 | MIT | UI component library. Builds the ticket form, ticket list, chat interface, and landing page. |
| **React DOM** | 19.1.0 | MIT | React renderer for web browsers. |
| **Vite** | 6.3.5 | MIT | Build tool and dev server. Provides instant hot module replacement (HMR) and API proxy to backend during development. |
| **Recharts** | 3.x | MIT | Interactive charts for analytics dashboard (bar, donut, area charts). Built on React and D3. |
| **react-force-graph-2d** | 1.29.1 | MIT | Force-directed graph visualization for the knowledge graph explorer. |
| **socket.io-client** | 4.8.3 | MIT | Real-time WebSocket client for live ticket update notifications. |

---

## 4. Development & Data Generation Tools

| Tool | License | Purpose |
|------|---------|---------|
| **OpenAI API (GPT-4o)** | Commercial | Used offline to generate 355 synthetic training tickets (of the 800-ticket corpus). Not used at runtime. |
| **Claude** | Commercial | Used via the Claude API to generate 164 edge-case training tickets. Not used at runtime. |
| **Phi-4 (phi4-mini)** | MIT | Used offline to generate 13 synthetic training tickets. Not used at runtime. |
| **Git + GitHub** | Open Source | Version control and collaboration. Monorepo structure with backend/ and frontend/ directories. |
| **GitHub Flow** | - | Branching strategy: feature branches → PR → main. No develop branch. |

---

## 5. Why These Choices

### ArangoDB over Neo4j + Pinecone + MongoDB
Traditional GraphRAG requires 3 separate databases: Neo4j (graph), Pinecone (vectors), MongoDB (documents). ArangoDB combines all three in one engine, eliminating:
- Cross-database synchronization complexity
- Multiple connection pools and failure modes
- Data consistency issues between stores

### Ollama over OpenAI API
- **Privacy**: Ticket data never leaves the network
- **Cost**: Zero API costs after setup
- **Latency**: No network round-trip to cloud
- **Reliability**: Works offline, no rate limits
- **Control**: Can switch models without code changes

### Qwen 2.5:7B over larger models
- Runs on CPU (no GPU required)
- 7B parameters provides strong reasoning for root-cause analysis (upgraded from 3B for better accuracy)
- OpenAI-compatible API means easy model swapping

### MiniLM over OpenAI Embeddings
- Runs locally (no API calls)
- 384 dimensions is sufficient for IT ticket similarity
- Fast: <500ms per embedding on CPU
- Well-established in the industry for semantic search

### FastAPI over Django/Flask
- Native async support (critical for parallel classifier execution)
- Automatic OpenAPI docs (no extra work)
- Pydantic integration (type-safe request/response handling)
- Best performance among Python web frameworks

---

## 6. License Compliance Summary

| License | Libraries | Commercial Use |
|---------|-----------|---------------|
| MIT | FastAPI, React, Vite, Recharts, Pydantic, python-arango, redis, python-jose, spaCy | Allowed |
| Apache 2.0 | ArangoDB, Docker, sentence-transformers, Qwen 2.5, MiniLM, Ollama, bcrypt | Allowed |
| BSD 3-Clause | Uvicorn, httpx, python-dotenv, Redis | Allowed |

All libraries used are **permissively licensed** and allow commercial use, modification, and distribution.
