from __future__ import annotations

import json
import logging
import re

from app.agents.document_intelligence import (
    DEFAULT_BY_TYPE,
    DocumentIntelligenceDecision,
)
from app.llm import get_chat_llm
from app.ontology import DOCUMENT_TYPES

logger = logging.getLogger(__name__)


def _heuristic_classify(filename: str, sample_text: str) -> DocumentIntelligenceDecision:
    name = filename.lower().replace("-", " ").replace("_", " ")
    text = sample_text.lower()[:4000]

    # Prefer research/arena reports before generic "notes" matches in body text
    if any(
        k in name or k in text
        for k in ("arenas of competition", "next big arenas", "mckinsey", "white paper", "whitepaper")
    ):
        return DEFAULT_BY_TYPE["Research Report"]
    if any(k in name or k in text for k in ("research", "analysis", "study", "findings", "institute")):
        return DEFAULT_BY_TYPE["Research Report"]
    if any(k in name for k in ("meeting notes", "meeting minutes")) or any(
        k in text[:500] for k in ("meeting notes", "attendees:", "action items")
    ):
        return DEFAULT_BY_TYPE["Meeting Notes"]
    if any(k in name or k in text for k in ("methodology", "framework", "playbook")):
        return DEFAULT_BY_TYPE["Methodology"]
    if any(k in name or k in text for k in ("contract", "agreement", "msa", "sow", "clause")):
        return DEFAULT_BY_TYPE["Contract"]
    if any(k in name or k in text for k in ("financial", "earnings", "10-k", "balance sheet")):
        return DEFAULT_BY_TYPE["Financial Report"]
    if any(k in name or k in text for k in ("strategy deck", "presentation", "slides")):
        return DEFAULT_BY_TYPE["Strategy Presentation"]
    if any(k in name or k in text for k in ("deliverable", "engagement", "recommendation", "proposal", "final report", "post implementation", "stratcore", "project atlas", "project orion")):
        return DEFAULT_BY_TYPE["Consulting Deliverable"]
    return DEFAULT_BY_TYPE["Other"]


async def classify_document(filename: str, sample_text: str) -> DocumentIntelligenceDecision:
    """Document Intelligence Agent — selects indexing strategy and stores rationale."""
    heuristic = _heuristic_classify(filename, sample_text)
    llm = get_chat_llm(temperature=0)
    if llm is None:
        return heuristic

    try:
        prompt = f"""
Classify this consulting-firm document and choose indexing strategies.
Allowed document types: {DOCUMENT_TYPES}

Filename: {filename}
Sample:
\"\"\"
{sample_text[:3500]}
\"\"\"

Return ONLY valid JSON with keys:
document_type, chunking_strategy, metadata_strategy, graph_strategy,
retrieval_strategy, rationale, confidence

chunking_strategy must be one of: semantic, hierarchical, section, clause, token
"""
        response = await llm.ainvoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return heuristic
        data = json.loads(match.group(0))
        decision = DocumentIntelligenceDecision.model_validate(data)
        if decision.document_type not in DOCUMENT_TYPES:
            decision.document_type = heuristic.document_type
        return decision
    except Exception as exc:
        logger.warning("Document intelligence LLM failed, using heuristic: %s", exc)
        return heuristic
