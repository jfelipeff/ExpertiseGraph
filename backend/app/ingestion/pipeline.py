from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.agents.document_intelligence import DocumentIntelligenceDecision
from app.chunking.adaptive import classify_document
from app.chunking.strategies import chunk_document
from app.extraction.entity_resolution import EntityResolver
from app.extraction.graph_extractor import GraphExtractor
from app.graph.neo4j_client import get_neo4j
from app.graph.writer import GraphWriter
from app.ingestion.embeddings import EmbeddingService
from app.ingestion.parser import parse_file

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict[str, Any]], None]

# In-memory job store mirrors Neo4j for fast polling
JOBS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_job(job_id: str) -> dict[str, Any] | None:
    return JOBS.get(job_id)


async def run_ingestion(
    firm: dict[str, str],
    file_paths: list[Path],
    job_id: str | None = None,
) -> dict[str, Any]:
    job_id = job_id or str(uuid.uuid4())
    client = get_neo4j()
    writer = GraphWriter(client)
    embedder = EmbeddingService()
    extractor = GraphExtractor()

    job: dict[str, Any] = {
        "id": job_id,
        "status": "running",
        "stage": "starting",
        "progress": 0,
        "firm_id": firm["id"],
        "files": [p.name for p in file_paths],
        "file_stages": {p.name: {"stage": "queued", "detail": ""} for p in file_paths},
        "decisions": {},
        "stats": {
            "documents": 0,
            "chunks": 0,
            "entities": 0,
            "relationships": 0,
        },
        "error": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    JOBS[job_id] = job
    writer.save_job(job)
    writer.upsert_firm(firm)

    try:
        # Concurrent per-file processing
        sem = asyncio.Semaphore(3)

        async def process_one(path: Path) -> dict[str, Any]:
            async with sem:
                return await _process_document(
                    path=path,
                    firm_id=firm["id"],
                    writer=writer,
                    embedder=embedder,
                    extractor=extractor,
                    job=job,
                )

        results = await asyncio.gather(*[process_one(p) for p in file_paths], return_exceptions=True)

        total_chunks = 0
        total_entities = 0
        total_rels = 0
        errors = []
        for path, result in zip(file_paths, results):
            if isinstance(result, Exception):
                job["file_stages"][path.name] = {"stage": "failed", "detail": str(result)}
                errors.append(f"{path.name}: {result}")
                continue
            total_chunks += result["chunks"]
            total_entities += result["entities"]
            total_rels += result["relationships"]

        job["stats"] = {
            "documents": len(file_paths) - len(errors),
            "chunks": total_chunks,
            "entities": total_entities,
            "relationships": total_rels,
        }
        job["status"] = "completed" if not errors else "completed_with_errors"
        job["stage"] = "done"
        job["progress"] = 100
        job["error"] = "; ".join(errors) if errors else None
        job["updated_at"] = _now()
        writer.save_job(job)
        return job
    except Exception as exc:
        logger.exception("Ingestion failed")
        job["status"] = "failed"
        job["stage"] = "failed"
        job["error"] = str(exc)
        job["updated_at"] = _now()
        writer.save_job(job)
        return job


async def _process_document(
    path: Path,
    firm_id: str,
    writer: GraphWriter,
    embedder: EmbeddingService,
    extractor: GraphExtractor,
    job: dict[str, Any],
) -> dict[str, Any]:
    name = path.name

    def set_stage(stage: str, detail: str = "", progress: int | None = None) -> None:
        job["file_stages"][name] = {"stage": stage, "detail": detail}
        job["stage"] = f"{name}:{stage}"
        if progress is not None:
            job["progress"] = progress
        job["updated_at"] = _now()
        JOBS[job["id"]] = job

    set_stage("parsing", "Extracting text", 10)
    parsed = await asyncio.to_thread(parse_file, path)
    pages = parsed.to_langchain_pages()
    if not pages:
        raise ValueError("No extractable text found")

    set_stage("classifying", "Document intelligence agent", 25)
    decision: DocumentIntelligenceDecision = await classify_document(
        filename=name,
        sample_text=parsed.full_text[:5000],
    )
    job["decisions"][name] = decision.model_dump()

    document_id = f"doc:{uuid.uuid5(uuid.NAMESPACE_URL, f'{firm_id}:{name}').hex}"
    writer.upsert_document(
        {
            "id": document_id,
            "filename": name,
            "document_type": decision.document_type,
            "chunking_strategy": decision.chunking_strategy,
            "decision_rationale": decision.rationale,
            "decision_confidence": decision.confidence,
            "firm_id": firm_id,
        }
    )

    set_stage("chunking", f"Strategy={decision.chunking_strategy}", 40)
    chunks = await asyncio.to_thread(chunk_document, pages, decision)

    set_stage("embedding", f"{len(chunks)} chunks", 55)
    embeddings = await embedder.embed_documents([c.page_content for c in chunks])

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{document_id}:chunk:{i}"
        writer.upsert_chunk(
            {
                "id": chunk_id,
                "text": chunk.page_content,
                "document_id": document_id,
                "page_number": chunk.metadata.get("page_number"),
                "position": i,
                "embedding": emb,
            }
        )

    set_stage("extracting", "Entity & relationship extraction", 70)
    local_resolver = EntityResolver()
    extractor.resolver = local_resolver
    rel_count = 0
    # Bound concurrency for LLM calls
    sem = asyncio.Semaphore(4)

    async def extract_one(i: int, chunk) -> int:
        async with sem:
            chunk_id = f"{document_id}:chunk:{i}"
            result = await extractor.extract_chunk(
                chunk=chunk,
                chunk_id=chunk_id,
                document_id=document_id,
                source_document=name,
            )
            for entity in local_resolver.all_entities():
                writer.upsert_entity_safe(entity, firm_id)
            for triple in result.triples:
                writer.upsert_relationship(triple)
            return len(result.triples)

    counts = await asyncio.gather(
        *[extract_one(i, chunk) for i, chunk in enumerate(chunks)]
    )
    rel_count = sum(counts)

    # Final entity upsert after full resolution pass
    for entity in local_resolver.all_entities():
        writer.upsert_entity_safe(entity, firm_id)

    set_stage("indexing", "Hybrid indexes ready", 95)
    set_stage("done", "Complete", 100)

    return {
        "chunks": len(chunks),
        "entities": len(local_resolver.all_entities()),
        "relationships": rel_count,
        "decision": decision.model_dump(),
    }
