from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.api.schemas import ChatIn, ExpertIn, JobOut
from app.config import get_settings
from app.demo_corpus import DEMO_FIRM, demo_file_paths, demo_graph_status, list_demo_documents
from app.graph.explorer import GraphExplorer
from app.graph.neo4j_client import get_neo4j
from app.ingestion.pipeline import get_job, run_ingestion
from app.retrieval.experts import ExpertDiscovery
from app.retrieval.gaps import KnowledgeGapEngine
from app.retrieval.hybrid import ChatService, HybridRetriever
from app.retrieval.insights import InsightService

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXT = {".pdf", ".docx", ".txt"}


@router.get("/health")
async def health():
    try:
        get_neo4j().verify()
        neo4j = "ok"
    except Exception as exc:
        neo4j = f"error: {exc}"
    return {"status": "ok", "neo4j": neo4j}


@router.post("/ingest", response_model=JobOut)
async def ingest(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    description: str = Form(""),
    industry: str = Form(""),
    notes: str = Form(""),
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(400, "At least one file is required")

    settings = get_settings()
    job_id = str(uuid.uuid4())
    job_dir = settings.upload_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    firm_id = f"firm:{uuid.uuid5(uuid.NAMESPACE_URL, name.strip().lower()).hex}"
    firm = {
        "id": firm_id,
        "name": name.strip(),
        "description": description,
        "industry": industry,
        "notes": notes,
    }

    saved: list[Path] = []
    display_names: list[str] = []
    for upload in files:
        original = Path(upload.filename or "upload.bin").name
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXT:
            raise HTTPException(400, f"Unsupported file type: {original}")
        dest = job_dir / original
        with dest.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        saved.append(dest)
        display_names.append(original)

    from app.ingestion import pipeline as pipe

    pipe.JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "firm_id": firm_id,
        "files": display_names,
        "file_stages": {n: {"stage": "queued", "detail": ""} for n in display_names},
        "decisions": {},
        "stats": {},
        "error": None,
    }

    background_tasks.add_task(_bg_ingest, firm, saved, job_id)
    return JobOut(**pipe.JOBS[job_id])


async def _bg_ingest(firm, saved, job_id):
    await run_ingestion(firm=firm, file_paths=saved, job_id=job_id)


def _clear_knowledge_graph() -> None:
    """Wipe domain data so the example graph is clean (keeps ontology types)."""
    get_neo4j().run_write(
        """
        MATCH (n)
        WHERE n:Entity OR n:Document OR n:Chunk OR n:Firm OR n:IngestJob
        DETACH DELETE n
        """
    )


@router.get("/demo")
async def demo_info():
    from app.demo_seed import seed_status

    docs = list_demo_documents()
    status = demo_graph_status()
    seeding = seed_status()
    return {
        "mode": "example",
        "firm": DEMO_FIRM,
        "documents": docs,
        "description": (
            "The StratCore example graph is loaded once when the API deploys into Neo4j Aura, "
            "then shared with every visitor — no per-visit rebuild."
        ),
        **status,
        **seeding,
    }


def _cached_demo_job(display_names: list[str], status: dict) -> dict:
    return {
        "id": "demo-cached",
        "status": "completed",
        "stage": "cached",
        "progress": 100,
        "firm_id": DEMO_FIRM["id"],
        "files": display_names,
        "file_stages": {
            n: {"stage": "cached", "detail": "Using pre-built example graph (no LLM tokens)"}
            for n in display_names
        },
        "decisions": {},
        "stats": {
            "documents": status.get("documents", 0),
            "entities": status.get("entities", 0),
            "relationships": status.get("relationships", 0),
            "quality": status.get("quality"),
            "cached": True,
        },
        "error": None,
        "mode": "demo",
    }


@router.post("/demo/start", response_model=JobOut)
async def demo_start(background_tasks: BackgroundTasks, reset: bool = False):
    """Open the shared example graph, or rebuild when reset=true.

    Default (reset=false): if StratCore is already in Neo4j, return a completed cached job
    and do not call the LLM. reset=true wipes domain data and re-ingests (uses tokens).
    """
    paths = demo_file_paths()
    if not paths:
        raise HTTPException(
            404,
            "No demo PDFs found in sample_docs/. Expected StratCore Atlas/Orion reports.",
        )

    display_names = [p.name for p in paths]
    status = demo_graph_status()

    if status.get("graph_ready") and not reset:
        job = _cached_demo_job(display_names, status)
        from app.ingestion import pipeline as pipe

        pipe.JOBS[job["id"]] = job
        return JobOut(**{k: v for k, v in job.items() if k != "mode"})

    if reset:
        try:
            _clear_knowledge_graph()
        except Exception as exc:
            logger.warning("Demo reset failed: %s", exc)

    job_id = str(uuid.uuid4())

    from app.ingestion import pipeline as pipe

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

    background_tasks.add_task(_bg_ingest, DEMO_FIRM, paths, job_id)
    return JobOut(**{k: v for k, v in pipe.JOBS[job_id].items() if k != "mode"})


@router.get("/jobs/{job_id}", response_model=JobOut)
async def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        # Try Neo4j
        row = get_neo4j().run(
            "MATCH (j:IngestJob {id: $id}) RETURN j {.*, id: j.id} AS job",
            {"id": job_id},
        )
        if not row:
            raise HTTPException(404, "Job not found")
        job = row[0]["job"]
    return JobOut(
        id=job["id"],
        status=job.get("status", "unknown"),
        stage=job.get("stage", ""),
        progress=int(job.get("progress") or 0),
        file_stages=job.get("file_stages") or {},
        decisions=job.get("decisions") or {},
        stats=job.get("stats") or {},
        error=job.get("error"),
    )


@router.get("/graph")
async def get_graph(limit_nodes: int = 300, limit_edges: int = 600):
    return GraphExplorer(get_neo4j()).full_graph(limit_nodes, limit_edges)


@router.get("/graph/search")
async def search_graph(q: str):
    return {"results": GraphExplorer(get_neo4j()).search_nodes(q)}


@router.get("/graph/nodes/{node_id:path}")
async def node_detail(node_id: str):
    detail = GraphExplorer(get_neo4j()).node_detail(node_id)
    if not detail:
        raise HTTPException(404, "Node not found")
    return detail


@router.get("/temporal")
async def temporal(days: int = 30):
    return GraphExplorer(get_neo4j()).temporal_changes(days)


@router.post("/chat")
async def chat(body: ChatIn):
    return await ChatService(get_neo4j()).answer(body.question)


@router.post("/retrieve")
async def retrieve(body: ChatIn):
    return await HybridRetriever(get_neo4j()).retrieve(body.question)


@router.post("/experts")
async def experts(body: ExpertIn):
    return ExpertDiscovery(get_neo4j()).find_experts(body.question)


@router.get("/gaps")
async def gaps(limit: int = 25):
    return KnowledgeGapEngine(get_neo4j()).detect(limit)


@router.get("/documents")
async def documents():
    rows = get_neo4j().run(
        """
        MATCH (d:Document)
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        RETURN d.id AS id,
               d.filename AS filename,
               d.document_type AS document_type,
               d.chunking_strategy AS chunking_strategy,
               d.decision_rationale AS decision_rationale,
               d.decision_confidence AS decision_confidence,
               count(c) AS chunks
        ORDER BY d.filename
        """
    )
    return {"documents": rows}


@router.get("/insights")
async def insights():
    return InsightService(get_neo4j()).build()
