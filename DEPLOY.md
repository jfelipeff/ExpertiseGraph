# Deploy ExpertiseGraph (Vercel free + free companions)

Vercel **Hobby/free cannot run Neo4j or long FastAPI ingest jobs**. The free layout is:

| Piece | Free host |
|-------|-----------|
| React UI | **Vercel** |
| FastAPI | **Render** free web service |
| Neo4j | **Neo4j AuraDB Free** |

## 1. Neo4j Aura Free

1. Create an instance at https://console.neo4j.io (Aura Free).
2. Copy **URI** (`neo4j+s://…`), username, password.

## 2. Backend on Render Free

1. Push this repo to GitHub.
2. In https://dashboard.render.com → **New → Blueprint** → select the repo (`render.yaml`).
3. Set env vars:
   - `NEO4J_URI` = Aura URI (`neo4j+s://…`)
   - `NEO4J_USERNAME` / `NEO4J_PASSWORD`
   - `XAI_API_KEY` = your Grok key
   - `LLM_MODEL` = `grok-3-mini`
4. After deploy, copy the API URL, e.g. `https://expertisegraph-api.onrender.com`.

Local smoke test against Aura (optional):

```bash
export NEO4J_URI='neo4j+s://xxxx.databases.neo4j.io'
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD='…'
export XAI_API_KEY='…'
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 3. Frontend on Vercel Free

From `frontend/`:

```bash
cd frontend
npx vercel login
npx vercel link   # create new project
npx vercel env add VITE_API_URL production
# paste: https://YOUR-RENDER-API.onrender.com/api
npx vercel --prod
```

`VITE_API_URL` must include `/api` (no trailing slash), e.g. `https://expertisegraph-api.onrender.com/api`.

## Notes

- Render free **spins down** after idle; first request can take ~30–60s.
- Uploads on Render free are **ephemeral** (disk resets on restart); demo PDFs are baked into the Docker image.
- Do not commit `.env`.
