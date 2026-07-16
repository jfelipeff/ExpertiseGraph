from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.ontology import DOCUMENT_TYPES


ChunkStrategy = Literal[
    "semantic",
    "hierarchical",
    "section",
    "clause",
    "token",
]


class DocumentIntelligenceDecision(BaseModel):
    document_type: str = Field(description="Classified document type")
    chunking_strategy: ChunkStrategy
    metadata_strategy: str
    graph_strategy: str
    retrieval_strategy: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


DEFAULT_BY_TYPE: dict[str, DocumentIntelligenceDecision] = {
    "Meeting Notes": DocumentIntelligenceDecision(
        document_type="Meeting Notes",
        chunking_strategy="semantic",
        metadata_strategy="participants_topics_actions",
        graph_strategy="people_projects_topics",
        retrieval_strategy="hybrid_temporal",
        rationale="Meeting notes benefit from semantic turns and participant-centric graph links.",
        confidence=0.85,
    ),
    "Consulting Deliverable": DocumentIntelligenceDecision(
        document_type="Consulting Deliverable",
        chunking_strategy="section",
        metadata_strategy="client_engagement_findings",
        graph_strategy="client_project_capability",
        retrieval_strategy="hybrid_section_aware",
        rationale="Deliverables are structured by sections; preserve section boundaries.",
        confidence=0.9,
    ),
    "Methodology": DocumentIntelligenceDecision(
        document_type="Methodology",
        chunking_strategy="hierarchical",
        metadata_strategy="framework_steps",
        graph_strategy="methodology_capability",
        retrieval_strategy="graph_first",
        rationale="Methodologies are hierarchical; keep parent/child structure.",
        confidence=0.9,
    ),
    "Financial Report": DocumentIntelligenceDecision(
        document_type="Financial Report",
        chunking_strategy="section",
        metadata_strategy="metrics_periods",
        graph_strategy="company_metrics",
        retrieval_strategy="hybrid",
        rationale="Financial reports are sectioned; keep metric context intact.",
        confidence=0.8,
    ),
    "Research Report": DocumentIntelligenceDecision(
        document_type="Research Report",
        chunking_strategy="semantic",
        metadata_strategy="claims_evidence",
        graph_strategy="topic_entity_dense",
        retrieval_strategy="hybrid",
        rationale="Research needs semantic claim/evidence chunks for GraphRAG.",
        confidence=0.85,
    ),
    "Contract": DocumentIntelligenceDecision(
        document_type="Contract",
        chunking_strategy="clause",
        metadata_strategy="parties_obligations",
        graph_strategy="parties_obligations",
        retrieval_strategy="precise_clause",
        rationale="Contracts must stay clause-aware for legal provenance.",
        confidence=0.92,
    ),
    "Strategy Presentation": DocumentIntelligenceDecision(
        document_type="Strategy Presentation",
        chunking_strategy="section",
        metadata_strategy="slides_themes",
        graph_strategy="initiative_capability",
        retrieval_strategy="hybrid",
        rationale="Decks map to thematic sections / slides.",
        confidence=0.8,
    ),
    "White Paper": DocumentIntelligenceDecision(
        document_type="White Paper",
        chunking_strategy="semantic",
        metadata_strategy="thesis_arguments",
        graph_strategy="topic_entity_dense",
        retrieval_strategy="hybrid",
        rationale="White papers are argumentative; semantic chunking preserves thesis flow.",
        confidence=0.85,
    ),
    "Other": DocumentIntelligenceDecision(
        document_type="Other",
        chunking_strategy="token",
        metadata_strategy="generic",
        graph_strategy="general_ontology",
        retrieval_strategy="hybrid",
        rationale="Fallback to token chunking with general ontology extraction.",
        confidence=0.5,
    ),
}


@dataclass
class ClassificationInput:
    filename: str
    sample_text: str
