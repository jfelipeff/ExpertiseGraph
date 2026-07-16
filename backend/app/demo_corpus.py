from __future__ import annotations

from pathlib import Path

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
        Path("/app/sample_docs"),
        settings.upload_dir.parent / "sample_docs",
        Path(__file__).resolve().parents[2] / "sample_docs",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


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
