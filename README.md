# ExpertiseGraph

Institutional-memory MVP: upload consulting knowledge, build a Neo4j knowledge graph with Grok + LangChain `LLMGraphTransformer`, and ask grounded GraphRAG questions.

## Local run

```bash
cp .env.example .env   # set XAI_API_KEY
docker compose up --build
```

- App: http://localhost:5173
- API: http://localhost:8000/docs

## Free cloud hosting (Vercel + Render + Aura)

Vercel free hosts the **frontend only**. Full steps: see **[DEPLOY.md](./DEPLOY.md)**.
