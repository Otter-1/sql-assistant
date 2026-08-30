# SQL Assistant — Hybrid Text-to-SQL for Production & Maintenance Data

![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1c3c5c?logo=langchain)
![DuckDB](https://img.shields.io/badge/DuckDB-OLAP-fff000?logo=duckdb)
![React](https://img.shields.io/badge/React-19-61dafb?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-6-3178c6?logo=typescript)
![License](https://img.shields.io/badge/License-MIT-green)

An assistant that lets you **talk to tabular data in natural language**. You
ask a question in English, it translates it to SQL, executes it against a
relational database and answers with figures, the source, and an insight.

Target architecture: **plug-and-play** — index any relational database
(PostgreSQL / DuckDB / SQLite) and query it, with **zero per-deployment
curation**.

Case study: industrial production and maintenance data. The data is a
fictional demonstration dataset.

## Demo

![Demo of the SQL assistant](assets/demo.gif)

*Ask a question in English → SQL generation → execution → fact-based answer
with source and insight, streamed in real time.*

## Why Hybrid Text-to-SQL?

The starting premise: **talk to tabular data in natural language**. Three
structuring choices (reframe, Aug 2026):

- **Text-to-SQL, not document RAG** — the data is structured (production,
  maintenance, downtime). No documents to index. SQL is exact and traceable.
- **Hybrid retrieval** — vector indexes over the *schema* (which tables to
  query) and over *values* (which literals to filter on), so the LLM only sees
  a pruned sub-schema instead of the full one.
- **Semantic cache as the fast path** — no semantic layer, no intent router.
  Repeated/close questions are replayed deterministically from a learned cache;
  the LLM is only called for genuinely new questions.

## Stack

| Layer | Technology |
|---|---|
| Backend | LangGraph 1.2 + DeepSeek V4 Flash (OpenRouter) + SQLAlchemy |
| Execution | DuckDB (demo) / PostgreSQL / SQLite — read-only |
| Retrieval | local sentence-transformers embeddings + Chroma embedded (on-disk) |
| Frontend | Vite + React 19 + shadcn/ui + Tailwind v4 |
| Streaming | `@langchain/react` — `useStream` hook |
| Agent | `create_agent()` (model → tools → model) + `trim_memory` middleware |

## Structure

```
├── backend/           ← Agent LangGraph + indexing + execution
│   ├── src/agent.py   # Main agent + title generator
│   ├── src/loader.py  # Schema metadata extraction + profiling (PostgreSQL)
│   ├── src/datamodels.py  # Pydantic schema index models + get_pruned_schema
│   ├── src/queries.py     # Profiling SQL queries (cardinality, samples)
│   ├── sql/inspect_ddl.sql  # Bulk schema extraction query (single source)
│   ├── langgraph.json  # Graph declarations
│   └── schema.md       # DuckDB schema (injected into the prompt for now)
├── frontend/          ← React interface (English UI)
│   └── src/
│       ├── Chat.tsx          # Chat component + streaming
│       ├── App.tsx           # Orchestrator
│       └── hooks/            # localStorage conversation management
```

## Running it

```bash
# Backend
cd backend
source .venv/bin/activate
langgraph dev --host 0.0.0.0 --port 2024

# Frontend (another terminal)
cd frontend
npm run dev
```

## Agent pipelines

- **Main agent** (`agent`) — `create_agent()` with the `query_db(sql)` tool
  that executes SQL (DuckDB today; multi-engine SQLAlchemy planned) and
  returns a DataFrame as text. English system prompt with the injected schema;
  `trim_memory` keeps the last 10 messages.
- **Title generation** (`title-generator`) — tool-free agent, single model
  call, produces a 3-6 word English title after the first message.

## Business rules (agent)

- Language: questions and answers in **English**
- SQL: **SELECT only, never DML**, dialect of the target database
- Format: question → SQL (code block) → figures → source → insight
- Precision: exact values with units, no "approximately"
- Limit: 10 results unless explicitly requested

## Architecture details

See `backend/schema.md` for the database schema, and
`docs/internal/ARCHITECTURE_V2.md` (local only) for the reframed hybrid
blueprint: ingestion pipeline, runtime retrieval, decisions, and research
grounding (CHESS, BIRD, DIN-SQL, MAC-SQL).

## Roadmap

Current state and next steps.

### Done

- [x] LangGraph agent with `query_db` tool + `trim_memory`
- [x] Conversation title generation (dedicated agent)
- [x] React frontend + real-time streaming (`useStream`)
- [x] Conversation persistence (localStorage)
- [x] Schema metadata extractor (structure, PK/FK — `src/loader.py`)
- [x] Column profiling (cardinality, distinct values, samples)
- [x] English port of the product (prompts, UI, comments)

### Indexing (P1 — in progress)

- [ ] Table summaries (descriptions) for the schema index
- [ ] Multi-dialect extraction (DuckDB / SQLite) — `queries.py` is PG-only
- [ ] `schema_metadata.json` export (structured index)
- [ ] Embeddings → `schema_store` (tables/columns) + `value_store` (values)

### Runtime (P2)

- [ ] Read-only multi-engine execution (SQLAlchemy: PG/DuckDB/SQLite)
- [ ] Context assembly via `get_pruned_schema()` (PK/FK always kept)
- [ ] Schema linker (which tables) + entity resolver (which literals)
- [ ] EXPLAIN validation loop before execution
- [ ] Wire the frontend database selector to a real `/databases` endpoint

### Learning & hardening (P3)

- [ ] Semantic cache + dynamic few-shot (cache-first fast path)
- [ ] Unit tests (SQL generation, DML refusal, edge cases)
- [ ] Docker Compose (`docker compose up` = everything runs)
- [ ] Larger dataset (10k+ rows)
- [ ] Robust error handling (timeout, retry, fallback model)
- [ ] Thread persistence via PostgreSQL (`langgraph up`)