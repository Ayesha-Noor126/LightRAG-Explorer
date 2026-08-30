# LightRAG Explorer

**Tech Stack**

![Python](https://img.shields.io/badge/Python-3.11-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-5-646cff?style=flat-square&logo=vite&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5.24-008cc1?style=flat-square&logo=neo4j&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-green?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)
![Langfuse](https://img.shields.io/badge/Langfuse-Observability-orange?style=flat-square)
![LightRAG](https://img.shields.io/badge/LightRAG-Graph%20RAG-purple?style=flat-square)

A full-stack research platform that implements, compares, and evaluates two fundamentally different Retrieval-Augmented Generation architectures side-by-side: **Simple RAG** (vector similarity search) and **LightRAG** (graph-based retrieval with entity/relationship extraction). Built to answer a real research question — *when does a knowledge graph actually beat a vector store, and on what types of questions?*

---

## Project Statement

RAG systems have become the standard way to ground large language model answers in private documents. The dominant approach — chunk the text, embed it, retrieve by cosine similarity, pass to an LLM — works well for direct lookup questions. But it has known limitations on questions that require reasoning across multiple entities, following chains of relationships, or synthesising information spread across many parts of a corpus.

**LightRAG** (from the paper *LightRAG: Simple and Fast Retrieval-Augmented Generation*, University of Hong Kong, 2024) proposes an alternative: extract entities and relationships from documents into a knowledge graph, then use graph traversal (local, global, hybrid, mix) alongside vector search to answer queries. The paper claims substantial improvements on multi-hop and relationship-centric questions.

This project **builds both pipelines from scratch, runs them on the same documents, asks them the same questions, and measures the difference** — across four query categories designed to stress-test each architecture differently. It also adds a summarisation layer on top of Simple RAG to partially close the gap, and integrates Langfuse observability to trace LightRAG's internal retrieval behaviour per query.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                       │
│  Simple RAG │ LightRAG │ Comparison │ Graph │ Analytics  │
│             │          │  + Eval    │  View │  + Expts   │
└────────────────────────┬─────────────────────────────────┘
                         │ REST (Axios, port 8000)
┌────────────────────────▼─────────────────────────────────┐
│               FastAPI Backend (Python 3.11)              │
│                                                          │
│  Simple RAG Pipeline          LightRAG Pipeline          │
│  ┌──────────────────┐         ┌──────────────────┐       │
│  │ Extract → Chunk  │         │  Ingestion →     │       │
│  │ Embed (local)    │         │  LightRAG HTTP   │       │
│  │ ChromaDB store   │         │  /documents/text │       │
│  │ Summarise (LLM)  │         │                  │       │
│  │ Retrieve → LLM   │         │  Query →         │       │
│  └──────────────────┘         │  LightRAG HTTP   │       │
│                               │  /query          │       │
│  Langfuse SDK ─────────────── │  sub-query trace │       │
│  Neo4j driver (read-only) ─── └──────────────────┘       │
│  Experiment registry (JSON)                              │
└──────────┬───────────────────────────┬───────────────────┘
           │ Bolt (7687)               │ HTTP (9621)
┌──────────▼──────┐          ┌─────────▼────────────────┐
│   Neo4j 5.24    │◄─────────│   LightRAG Server        │
│  Knowledge Graph│  writes  │  (ghcr.io/hkuds/lightrag)│
│  84+ nodes      │  graph   │  Gemini LLM + Embeddings │
│  86+ edges      │          │  Neo4JStorage backend    │
└─────────────────┘          └──────────────────────────┘
           │
┌──────────▼──────┐
│  Langfuse Cloud │
│  Trace per query│
│  sub-query count│
│  span breakdown │
└─────────────────┘
```

---

## What Makes This Project Stand Out

### 1. Dual pipeline, same documents, same questions
Both systems ingest the same uploaded documents. The Comparison tab fires both pipelines concurrently with a single question and renders answers, retrieved evidence, and latency side-by-side. This is the same experimental design used in the LightRAG paper — implemented as a live, interactive tool rather than a static script.

### 2. Summarisation layer on Simple RAG
Standard Simple RAG passes raw chunk text to the LLM. This project adds a pre-generation step at ingest time: every chunk gets a 3–5 sentence dense summary (via Gemini), and the whole document gets an 8-sentence overview. Both are stored in a parallel ChromaDB collection (`simple_rag_summaries`). At query time, summaries are retrieved with a single key-value batch lookup (zero LLM calls, near-zero latency). This directly addresses one of the known limitations of Simple RAG — the LLM receiving noisy, decontextualised text fragments — and brings it closer to LightRAG's structured context assembly.

### 3. Langfuse observability on LightRAG
LightRAG is a black box — you send a query, get an answer. This project instruments every query with a two-span Langfuse trace: a `context-retrieval` span (the `only_need_context=True` call) and an `answer-generation` span. The `sub_query_count` metric is computed per query by counting the distinct retrieval sections (Entities, Relationships, Sources, Reports) in LightRAG's assembled context block. You can see in the Langfuse dashboard exactly how many internal retrievals each mode triggers and how that changes with query type.

### 4. Live knowledge graph visualisation
The Graph tab reads Neo4j directly via Bolt (decoupled from LightRAG's API) using a custom force-directed physics simulation — no external graph library. Nodes are sized by degree, coloured by entity type (8 categories), edges show directionality with arrows and relationship descriptions on hover. Full zoom/pan, search filter, top-hubs list, and a node detail panel showing the entity's description and all connected relationships.

### 5. Experiment Mode with growth tracking
The Experiment Mode tab lets you record timestamped snapshots (documents, chunks, entities, relationships, graph density) at each corpus size checkpoint. The Analytics dashboard plots Entities / Relationships / Chunks growth as a line chart across snapshots, making the graph construction cost vs retrieval quality trade-off visible over time.

### 6. Four structured query categories
The Comparison tab includes a `QueryCategories` panel with pre-built questions across four categories, each targeting a known architectural difference:
- **Single-document lookup** — Simple RAG's home ground
- **Cross-document synthesis** — where graph traversal should help
- **Multi-hop reasoning** — requires following entity relationships across hops
- **Relationship-centric** — directly tests the graph's edge data

---

## Folder Structure

```
lightrag-explorer/
│
├── docker-compose.yml          # Stands up backend, LightRAG server, Neo4j
├── PHASES.md                   # Build plan (all 3 phases complete)
├── .env                        # Root-level env (GEMINI_API_KEY propagated to compose)
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env                    # Backend runtime config (copy from .env.example)
│   ├── .env.example            # All configurable keys documented
│   │
│   └── app/
│       ├── main.py             # FastAPI app, CORS, router registration
│       ├── config.py           # Pydantic Settings — all values env-overridable
│       │
│       ├── models/
│       │   └── schemas.py      # All Pydantic request/response models
│       │
│       ├── routers/
│       │   ├── documents.py    # Upload, list, delete, rebuild
│       │   ├── query.py        # POST /api/query/simple-rag
│       │   ├── graphrag.py     # POST /api/query/lightrag, GET /api/graph/*
│       │   ├── comparison.py   # POST /api/query/compare (concurrent)
│       │   ├── analytics.py    # GET /api/analytics
│       │   └── experiments.py  # POST/GET/DELETE /api/experiments
│       │
│       └── services/
│           ├── document_processor.py   # Extract (PDF/DOCX/TXT/MD) + chunk
│           ├── embedding_service.py    # Sentence Transformers (local, cached)
│           ├── vector_store.py         # ChromaDB wrapper (chunks + summaries)
│           ├── llm_service.py          # Gemini: answer + chunk summary + doc summary
│           ├── simple_rag_service.py   # Full Simple RAG orchestration
│           ├── ingestion_service.py    # Dual-index: Simple RAG + LightRAG
│           ├── lightrag_service.py     # LightRAG HTTP client + Langfuse tracing
│           ├── neo4j_service.py        # Direct Neo4j Bolt reads (graph stats + data)
│           ├── tracing_service.py      # Langfuse client, spans, sub-query counting
│           ├── document_registry.py    # JSON-backed document metadata store
│           └── experiment_registry.py  # JSON-backed experiment snapshot store
│
└── frontend/
    ├── index.html
    ├── package.json            # React 18, Vite, Tailwind, Recharts, Axios
    ├── vite.config.js          # Proxy /api → localhost:8000
    │
    └── src/
        ├── App.jsx             # Root layout, tab routing, global state
        ├── api/
        │   └── client.js       # All API calls (Axios, 120s timeout)
        │
        └── components/
            ├── Sidebar.jsx         # Upload, document list, delete, rebuild
            ├── MetricsBar.jsx      # Live doc/chunk/entity counts
            ├── Tabs.jsx            # Tab navigation
            ├── QueryPanel.jsx      # Simple RAG query UI
            ├── AnswerDisplay.jsx   # Answer + chunk summaries + doc summaries
            ├── LightRAGPanel.jsx   # LightRAG query UI (mode selector)
            ├── ComparisonView.jsx  # Side-by-side query + latency bars
            ├── QueryCategories.jsx # Pre-built questions by category
            ├── GraphView.jsx       # Force-directed Neo4j graph (SVG, no lib)
            ├── AnalyticsDashboard.jsx  # Bar + line charts (Recharts)
            └── ExperimentMode.jsx  # Snapshot recording + history table
```

---

## Technology Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Google Gemini (`gemini-3.5-flash-lite`) | Low latency, cost-efficient, same model for both pipelines so comparisons are fair |
| Embeddings (Simple RAG) | `all-MiniLM-L6-v2` (Sentence Transformers, local) | Zero API cost per query, runs on CPU, deterministic |
| Embeddings (LightRAG) | `gemini-embedding-001` | Required by LightRAG's Gemini binding |
| Vector store | ChromaDB (persistent, two collections) | Lightweight, file-backed, no separate server |
| Graph database | Neo4j 5.24 | LightRAG's native graph backend; also read directly for the Graph tab |
| Graph RAG engine | LightRAG (`ghcr.io/hkuds/lightrag`) | Official Docker image, 5 retrieval modes, Neo4j storage |
| Backend | FastAPI + Uvicorn (Python 3.11) | Async, typed, auto-docs at `/docs` |
| Frontend | React 18 + Vite + Tailwind CSS | Fast HMR in dev, minimal bundle |
| Charts | Recharts | Corpus overview bar chart + experiment growth line chart |
| Observability | Langfuse | Per-query trace with sub-query count, context retrieval span, generation span |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX) | Format-native extraction, better than plain text conversion |

---

## Running the Project

### Prerequisites
- Docker Desktop (running)
- Node.js 18+
- A Gemini API key

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd lightrag-explorer
```

Copy the backend env file and add your keys:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite

# Optional: Langfuse observability
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

### 2. Start the backend services

```bash
docker compose up -d --build
```

This starts three containers:

| Container | Port | Role |
|---|---|---|
| `lightrag-explorer-backend` | 8000 | FastAPI — Simple RAG, graph queries, analytics |
| `lightrag-explorer-lightrag` | 9621 | LightRAG server — entity extraction, graph querying |
| `lightrag-explorer-neo4j` | 7474 / 7687 | Neo4j — knowledge graph storage |

Wait ~30 seconds for Neo4j's health check to pass before LightRAG starts. First build downloads PyTorch (~200 MB) and takes 5–10 minutes. Subsequent builds use the Docker layer cache.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### 4. Verify services

```
GET http://localhost:8000/docs        → FastAPI auto-docs
GET http://localhost:9621/health      → LightRAG health
http://localhost:7474                 → Neo4j Browser (neo4j / password123)
```

---

## Using the Application

### Upload documents
Drag and drop PDFs, DOCX, TXT, or MD files into the sidebar. Each document is:
1. Extracted and chunked (configurable size/overlap)
2. Embedded and stored in ChromaDB
3. Summarised (per-chunk and document-level) via Gemini and stored in a parallel ChromaDB collection
4. Sent to LightRAG for entity/relationship extraction into Neo4j
5. Tracked with dual status (Simple RAG status + Graph RAG status) in the sidebar

### Query tabs

**Simple RAG** — standard vector similarity retrieval. Returns answer, retrieved chunks with similarity scores, pre-generated chunk summaries, and document-level overviews.

**LightRAG** — graph-augmented retrieval. Choose a mode:
- `naive` — keyword only (1 retrieval)
- `local` — entity neighbourhood (2 retrievals)
- `global` — community summary (2 retrievals)
- `hybrid` — local + global (3 retrievals)
- `mix` — all modes combined (4 retrievals)

**Comparison** — sends the same question to both systems simultaneously, renders answers side by side with a latency bar chart. Use the Query Categories panel to try pre-built questions designed to highlight each system's strengths.

**Graph** — live Neo4j visualisation. Force-directed layout, entity-type colour coding, directed relationship arrows, zoom/pan, node search, relationship descriptions in the detail panel.

**Analytics** — document metrics, knowledge graph metrics, corpus overview bar chart, graph growth line chart from recorded experiment snapshots.

**Experiment Mode** — record corpus-size snapshots (after 1, 5, 20, 100 documents) and compare entity/relationship/chunk counts over time.

---

## The Research Comparison

This project replicates — as a live tool — the core experimental design of the LightRAG paper. Both papers and practical experience show the following pattern:

| Query type | Simple RAG | LightRAG |
|---|---|---|
| Direct fact lookup from a single passage | Fast, accurate | Slower, comparable accuracy |
| Concept that appears in multiple chunks | May miss connections | Traverses entity graph across documents |
| Multi-hop ("who is connected to X through Y?") | Often fails — no chain reasoning | Follows relationship edges across hops |
| Relationship-centric ("how does A relate to B?") | Returns passages mentioning both | Returns the actual extracted relationship |
| Large corpus (100+ docs) | Stable latency | Higher indexing cost, richer graph |

The Comparison tab and Query Categories panel are built around these four types so you can reproduce the pattern yourself with your own documents.

### Why the summarisation layer matters

Standard Simple RAG sends raw chunk text to the LLM — often 1000 characters of decontextualised prose that may lack the sentence introducing the concept. The summarisation layer pre-processes each chunk at ingest time into a dense 3–5 sentence paragraph capturing key facts, concepts, and conclusions. This brings two benefits:

1. **Faster comprehension** — the chunk's summary is available instantly at query time with zero LLM calls (key-value lookup from ChromaDB)
2. **Better LLM input** — the answer generation model receives cleaner, denser context rather than mid-sentence text fragments

This partially closes the quality gap between Simple RAG and LightRAG on single-document and direct-lookup questions without the graph's indexing cost.

### Langfuse: observing LightRAG from the outside

LightRAG's internal sub-query fan-out is not exposed by its public API. This project estimates it per query by counting distinct retrieval section headers (`Entities`, `Relationships`, `Sources`, `Reports`) in the context block LightRAG returns from `only_need_context=True`. The count is recorded as `sub_query_count` on the Langfuse trace alongside `context_retrieval_ms` and `generation_ms`. In practice:
- `naive` mode: 1 sub-query
- `local` / `global`: 2 sub-queries
- `hybrid`: 3 sub-queries
- `mix`: 4 sub-queries

This makes the latency vs. depth trade-off directly observable in the Langfuse dashboard.

---

## Configuration Reference

All values in `backend/.env` are overridable. Key settings:

```env
# Chunking
CHUNK_SIZE=1000          # characters per chunk
CHUNK_OVERLAP=150        # overlap between adjacent chunks
TOP_K=5                  # chunks retrieved per query

# Summarisation
SUMMARY_CHUNK_MAX_CHARS=3000   # max chars fed to chunk summariser
SUMMARY_DOC_MAX_CHARS=20000    # max chars fed to doc summariser

# Graph
GRAPH_VIEW_NODE_LIMIT=150      # max nodes shown in the Graph tab

# LightRAG
LIGHTRAG_REQUEST_TIMEOUT_S=120
LIGHTRAG_DEFAULT_MODE=hybrid
```

---

## API Reference

Full interactive docs at `http://localhost:8000/docs`. Key endpoints:

```
POST /api/documents/upload          Upload one or more files
GET  /api/documents                 List all documents + dual status
DELETE /api/documents/{id}          Delete document + summaries + graph data
POST /api/documents/rebuild         Re-chunk, re-embed, re-summarise all docs

POST /api/query/simple-rag          Simple RAG query (returns summaries)
POST /api/query/lightrag            LightRAG query (returns entities + relationships)
POST /api/query/compare             Concurrent comparison query

GET  /api/graph/stats               Node count, edge count, density, avg degree
GET  /api/graph/data?limit=150      Nodes + edges for visualisation
GET  /api/graph/health              Neo4j + LightRAG reachability

GET  /api/analytics                 Full metrics (docs, chunks, graph, last indexed)
POST /api/experiments               Record a corpus snapshot
GET  /api/experiments               List all recorded snapshots
```

---

## Screenshots



## Acknowledgements

- [LightRAG paper](https://arxiv.org/abs/2410.05779) — Zirui Guo et al., University of Hong Kong, 2024
- [LightRAG GitHub](https://github.com/HKUDS/LightRAG) — official implementation and Docker image
- [Langfuse](https://langfuse.com) — open-source LLM observability platform
- [ChromaDB](https://www.trychroma.com) — embedding database
- [Neo4j](https://neo4j.com) — graph database
