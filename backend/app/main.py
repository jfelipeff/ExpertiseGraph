from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.graph.neo4j_client import get_neo4j
from app.graph.schema import init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # Retry Neo4j briefly on startup (compose race)
    import asyncio

    client = get_neo4j()
    neo_ok = False
    for attempt in range(30):
        try:
            client.verify()
            init_schema(client)
            logger.info("Neo4j connected and schema initialized")
            neo_ok = True
            break
        except Exception as exc:
            logger.warning("Waiting for Neo4j (%s/30): %s", attempt + 1, exc)
            await asyncio.sleep(2)
    else:
        logger.error("Neo4j unavailable at startup — API will still boot")

    # Persist example in Aura once per empty DB; later deploys/restarts reuse it
    seed_task = None
    if neo_ok and settings.seed_demo_on_startup:
        from app.demo_seed import ensure_demo_seeded

        seed_task = asyncio.create_task(ensure_demo_seeded())

    yield

    if seed_task and not seed_task.done():
        seed_task.cancel()
        try:
            await seed_task
        except asyncio.CancelledError:
            pass
    try:
        client.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
