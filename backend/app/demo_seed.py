from __future__ import annotations

import logging
import uuid
from typing import Any

from app.demo_corpus import DEMO_FIRM, demo_file_paths, demo_graph_status

logger = logging.getLogger(__name__)

_seeding = False
_seed_error: str | None = None
_seed_job_id: str | None = None


def seed_status() -> dict[str, Any]:
    return {
        "seeding": _seeding,
        "seed_error": _seed_error,
        "seed_job_id": _seed_job_id,
    }


async def ensure_demo_seeded() -> None:
    """Load the StratCore example into Neo4j once (on deploy/startup if missing).

    Aura keeps the graph across Render restarts, so later boots skip LLM work.
    """
    global _seeding, _seed_error, _seed_job_id

    status = demo_graph_status()
    if status.get("graph_ready"):
        logger.info(
            "Demo graph already loaded (quality=%s, entities=%s, relationships=%s) — not re-seeding",
            status.get("quality"),
            status.get("entities"),
            status.get("relationships"),
        )
        return

    paths = demo_file_paths()
    if not paths:
        logger.warning("Demo seed skipped: no sample_docs PDFs found")
        return

    _seeding = True
    _seed_error = None
    job_id = f"demo-seed-{uuid.uuid4().hex[:8]}"
    _seed_job_id = job_id

    from app.ingestion import pipeline as pipe
    from app.ingestion.pipeline import run_ingestion

    display_names = [p.name for p in paths]
    pipe.JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "firm_id": DEMO_FIRM["id"],
        "files": display_names,
        "file_stages": {n: {"stage": "queued", "detail": ""} for n in display_names},
        "decisions": {},
        "stats": {},
        "error": None,
        "mode": "demo",
    }

    logger.info("Seeding demo graph on startup (%s files)…", len(paths))
    try:
        await run_ingestion(firm=DEMO_FIRM, file_paths=paths, job_id=job_id)
        final = demo_graph_status()
        logger.info(
            "Demo seed finished (ready=%s, quality=%s, entities=%s)",
            final.get("graph_ready"),
            final.get("quality"),
            final.get("entities"),
        )
    except Exception as exc:
        _seed_error = str(exc)
        logger.exception("Demo seed failed: %s", exc)
    finally:
        _seeding = False
