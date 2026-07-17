from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.config import get_settings

DEMO_FIRM = {
    "id": "firm:demo-stratcore",
    "name": "StratCore Consulting",
    "description": (
        "Boutique management consulting firm specializing in telecom and digital transformation. "
        "Demo corpus uses internal-style project reports (Atlas and Orion)."
    ),
    "industry": "Management Consulting",
    "notes": "Example mode sample for ExpertiseGraph.",
}

# LLM-extracted edges use ~0.82; heuristic co-occurrence uses ~0.58
_LLM_CONFIDENCE_FLOOR = 0.75

DEMO_DOC_META = {
    "StratCore_Project_Atlas_Final_Report.pdf": {
        "title": "Project Atlas — Final Report",
        "blurb": "TelecomCo GenAI readiness engagement: experts, use cases, architecture, and GraphRAG recommendation.",
        "year": 2025,
    },
    "StratCore_Project_Orion_Post_Implementation_Review.pdf": {
        "title": "Project Orion — Post-Implementation Review",
        "blurb": "Lessons from a prior StratCore engagement that informed Atlas recommendations.",
        "year": 2024,
    },
}


def sample_docs_dir() -> Path:
    settings = get_settings()
    candidates = [
        Path(os.environ["SAMPLE_DOCS_DIR"]) if os.environ.get("SAMPLE_DOCS_DIR") else None,
        Path("/app/sample_docs"),
        settings.sample_docs_dir,
        settings.upload_dir.parent / "sample_docs",
        Path(__file__).resolve().parents[2] / "sample_docs",
    ]
    for path in candidates:
        if path is not None and path.is_dir():
            return path
    return Path("/app/sample_docs")



def list_demo_documents() -> list[dict]:
    root = sample_docs_dir()
    docs = []
    if not root.exists():
        return docs
    for path in sorted(root.glob("*.pdf")):
        meta = DEMO_DOC_META.get(path.name, {})
        docs.append(
            {
                "filename": path.name,
                "title": meta.get("title", path.stem.replace("_", " ").replace("-", " ").title()),
                "blurb": meta.get("blurb", "Sample consulting document for demo graph."),
                "year": meta.get("year"),
                "size_mb": round(path.stat().st_size / (1024 * 1024), 1),
                "path": str(path),
            }
        )
    return docs


def demo_file_paths() -> list[Path]:
    root = sample_docs_dir()
    preferred = [
        root / "StratCore_Project_Atlas_Final_Report.pdf",
        root / "StratCore_Project_Orion_Post_Implementation_Review.pdf",
    ]
    paths = [p for p in preferred if p.exists()]
    if paths:
        return paths
    return sorted(root.glob("*.pdf"))


def expected_demo_filenames() -> list[str]:
    paths = demo_file_paths()
    if paths:
        return [p.name for p in paths]
    return list(DEMO_DOC_META.keys())


def demo_graph_status() -> dict[str, Any]:
    """Whether the shared Aura/Neo4j already holds the StratCore example corpus."""
    from app.graph.neo4j_client import get_neo4j

    expected = expected_demo_filenames()
    empty: dict[str, Any] = {
        "graph_ready": False,
        "quality": "empty",
        "documents": 0,
        "entities": 0,
        "relationships": 0,
        "llm_relationships": 0,
        "expected_documents": expected,
        "missing_documents": expected,
        "has_demo_firm": False,
    }
    try:
        neo = get_neo4j()
        doc_rows = neo.run(
            """
            MATCH (d:Document)
            WHERE d.filename IN $filenames
            RETURN collect(DISTINCT d.filename) AS present
            """,
            {"filenames": expected},
        )
        present = list((doc_rows[0].get("present") if doc_rows else None) or [])
        present = [p for p in present if p]

        firm_rows = neo.run(
            "MATCH (f:Firm {id: $firm_id}) RETURN count(f) AS n",
            {"firm_id": DEMO_FIRM["id"]},
        )
        has_firm = bool(firm_rows and (firm_rows[0].get("n") or 0) > 0)

        ent_rows = neo.run("MATCH (e:Entity) RETURN count(e) AS n")
        entities = int((ent_rows[0].get("n") if ent_rows else 0) or 0)

        rel_rows = neo.run(
            """
            MATCH ()-[r:RELATED]->()
            RETURN count(r) AS relationships,
                   sum(CASE WHEN coalesce(r.confidence, 0) >= $llm_floor THEN 1 ELSE 0 END) AS llm_relationships
            """,
            {"llm_floor": _LLM_CONFIDENCE_FLOOR},
        )
        relationships = int((rel_rows[0].get("relationships") if rel_rows else 0) or 0)
        llm_relationships = int((rel_rows[0].get("llm_relationships") if rel_rows else 0) or 0)
    except Exception:
        return empty

    missing = [n for n in expected if n not in present]
    graph_ready = len(missing) == 0 and entities > 0 and relationships > 0
    if llm_relationships > 0:
        quality = "llm"
    elif relationships > 0:
        quality = "heuristic"
    elif present:
        quality = "partial"
    else:
        quality = "empty"

    return {
        "graph_ready": graph_ready,
        "quality": quality,
        "documents": len(present),
        "entities": entities,
        "relationships": relationships,
        "llm_relationships": llm_relationships,
        "expected_documents": expected,
        "missing_documents": missing,
        "has_demo_firm": has_firm,
    }
