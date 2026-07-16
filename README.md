# ExpertiseGraph

Institutional-memory MVP: upload consulting knowledge, classify documents, adaptively chunk, extract an ontology-driven knowledge graph (Neo4j + LangChain `LLMGraphTransformer`), and ask grounded GraphRAG questions powered by **xAI Grok**.

No login/register — local demo only.

## Stack

| Layer | Choice |
|-------|--------|
| API | FastAPI + uvicorn |
| Graph DB | Neo4j 5 |
| LLM | **xAI Grok** via OpenAI-compatible API (`langchain-openai` + `https://api.x.ai/v1`) |
| Embeddings | Local deterministic vectors (no OpenAI required) |
| Graph extraction | `LLMGraphTransformer` when `XAI_API_KEY` / `GROK_API_KEY` is set |
| Chunking | Adaptive strategies + `TokenTextSplitter` |
| PDF | PyMuPDF |
| Frontend | React + TypeScript + Vite + Tailwind + React Flow |

## Quick start (Docker)

```bash
cd FulcrumsGraph   # project folder
cp .env.example .env
# Add your Grok key:
# XAI_API_KEY=xai-...

docker compose up --build
```

Open:

- App: http://localhost:5173
- API docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (neo4j / fulcrumgraph)

### Example mode

Choose **See how a graph looks** to load the arenas-of-competition sample corpus via `POST /api/demo/start`.

### Without a Grok key

Heuristic classification + keyword co-occurrence graph extraction still run. Set `XAI_API_KEY` (or `GROK_API_KEY`) for real LLM extraction and synthesized answers.

## Persistence

The UI restores mode, firm profile, sidebar selection, and graph visibility from `localStorage`, and reloads corpus insights/graph from Neo4j on refresh.
