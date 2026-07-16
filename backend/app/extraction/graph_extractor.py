from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer

from app.config import get_settings
from app.extraction.entity_resolution import EntityResolver
from app.llm import get_chat_llm
from app.ontology import ADDITIONAL_INSTRUCTIONS, ALLOWED_NODE_TYPES, ALLOWED_RELATIONSHIPS

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTriple:
    source_id: str
    source_name: str
    source_type: str
    relationship: str
    target_id: str
    target_name: str
    target_type: str
    evidence: str
    confidence: float
    chunk_id: str
    document_id: str
    page_number: int | None = None
    source_document: str | None = None


@dataclass
class ExtractionResult:
    triples: list[ExtractedTriple] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)


def _map_type(raw: str) -> str:
    cleaned = (raw or "Topic").strip()
    for allowed in ALLOWED_NODE_TYPES:
        if cleaned.lower() == allowed.lower():
            return allowed
    aliases = {
        "organization": "Company",
        "organisation": "Company",
        "org": "Company",
        "firm": "Company",
        "vendor": "Company",
        "partner": "Company",
        "customer": "Client",
        "client": "Client",
        "person": "Person",
        "employee": "Consultant",
        "consultant": "Consultant",
        "expert": "Consultant",
        "tool": "Technology",
        "software": "Technology",
        "tech": "Technology",
        "framework": "Methodology",
        "method": "Methodology",
        "approach": "Methodology",
        "sector": "Industry",
        "vertical": "Industry",
        "theme": "Topic",
        "concept": "Topic",
        "engagement": "Project",
        "program": "Initiative",
        "programme": "Initiative",
        "skill": "Capability",
        "service": "Capability",
    }
    return aliases.get(cleaned.lower(), "Topic")


def _map_rel(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z_]", "_", (raw or "RELATED_TO")).upper()
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned in ALLOWED_RELATIONSHIPS:
        return cleaned
    aliases = {
        "WORKS_ON": "WORKED_ON",
        "WORKEDON": "WORKED_ON",
        "USES": "USED",
        "USE": "USED",
        "AUTHOR": "AUTHORED",
        "WROTE": "AUTHORED",
        "IMPLEMENTS": "IMPLEMENTED",
        "SERVES": "FOR_CLIENT",
        "CLIENT_OF": "FOR_CLIENT",
        "RELATED": "RELATED_TO",
        "RELATES_TO": "RELATED_TO",
        "EXPERTISE": "EXPERT_IN",
        "SPECIALIZES_IN": "EXPERT_IN",
        "DEPENDS": "DEPENDS_ON",
        "PARTNER": "PARTNERS_WITH",
        "PARTNERSHIP": "PARTNERS_WITH",
        "MENTION": "MENTIONS",
    }
    return aliases.get(cleaned, "RELATED_TO")


class GraphExtractor:
    """LLM Graph Builder-style extraction with ontology constraints + provenance."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.resolver = EntityResolver()

    def _transformer(self) -> LLMGraphTransformer | None:
        """Match Neo4j LLM Graph Builder transformer setup for chat-style LLMs (e.g. Grok)."""
        llm = get_chat_llm(temperature=0)
        if llm is None:
            return None
        instructions = ADDITIONAL_INSTRUCTIONS.format(
            node_types=", ".join(ALLOWED_NODE_TYPES),
            rel_types=", ".join(ALLOWED_RELATIONSHIPS),
        )
        # Same branch llm-graph-builder uses when structured/tool calling is unreliable
        # (ChatGroq / many OpenAI-compatible providers): ignore_tool_usage=True, no prop schemas.
        return LLMGraphTransformer(
            llm=llm,
            allowed_nodes=ALLOWED_NODE_TYPES,
            allowed_relationships=ALLOWED_RELATIONSHIPS,
            node_properties=False,
            relationship_properties=False,
            ignore_tool_usage=True,
            additional_instructions=instructions,
        )

    def _heuristic_extract(
        self,
        chunk: Document,
        chunk_id: str,
        document_id: str,
        source_document: str,
    ) -> list[ExtractedTriple]:
        """Fallback keyword/entity extraction when no Grok key is configured."""
        text = chunk.page_content
        page_number = chunk.metadata.get("page_number")
        patterns = [
            # Companies / platforms
            (r"\b(Microsoft|Google|Alphabet|Amazon|Apple|Meta|NVIDIA|Nvidia|Intel|AMD|TSMC|Samsung|IBM|Oracle|Salesforce|Adobe|Uber|Airbnb|Netflix|Tesla|SpaceX|OpenAI|Anthropic|ByteDance|Alibaba|Tencent|Huawei|Siemens|GE|Boeing|Airbus|Toyota|Volkswagen|Shell|BP|ExxonMobil|McKinsey|Accenture|Deloitte|BCG|Bain)\b", "Company"),
            # Arenas / industries
            (r"\b(e-commerce|semiconductors?|electric vehicles?|cloud computing|cybersecurity|biotechnology|biopharma|fintech|climate tech|renewable energy|robotics|autonomous vehicles?|shared mobility|streaming video|digital advertising|software as a service|SaaS|artificial intelligence|generative AI|GenAI)\b", "Industry"),
            # Technologies
            (r"\b(AI|machine learning|deep learning|large language models?|LLMs?|GPUs?|chip ?manufacturing|batteries|lithium|hydrogen|5G|quantum computing|CRISPR|mRNA)\b", "Technology"),
            # Topics
            (r"\b(arenas? of competition|winner[- ]take[- ]most|network effects|economies of scale|productivity|innovation|capital intensity|market share|revenue pool)\b", "Topic"),
            # Geography-ish as Industry/Topic stand-ins
            (r"\b(United States|China|Europe|India|Japan|Southeast Asia)\b", "Industry"),
        ]
        found: list[tuple[str, str]] = []
        for pattern, etype in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found.append((match.group(1), etype))

        # Light proper-noun harvest for extra density (Title Case phrases)
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text):
            phrase = match.group(1)
            if phrase.lower() in {"the next", "exhibit", "exhibit source", "mckinsey global", "global institute"}:
                continue
            if len(phrase) < 6:
                continue
            found.append((phrase, "Topic"))

        # Dedupe while preserving order; cap per chunk
        seen = set()
        entities = []
        for name, etype in found:
            key = (name.lower(), etype)
            if key in seen:
                continue
            seen.add(key)
            entities.append(self.resolver.resolve(name, etype))
            if len(entities) >= 12:
                break

        triples: list[ExtractedTriple] = []
        # Prefer typed relationships when possible
        for i, src in enumerate(entities):
            for tgt in entities[i + 1 : i + 4]:
                if src.entity_type == "Company" and tgt.entity_type in {"Technology", "Industry", "Topic"}:
                    rel = "USED" if tgt.entity_type == "Technology" else "RELATED_TO"
                elif src.entity_type == "Technology" and tgt.entity_type == "Industry":
                    rel = "RELATED_TO"
                elif src.entity_type == "Company" and tgt.entity_type == "Company":
                    rel = "PARTNERS_WITH"
                else:
                    rel = "RELATED_TO"
                evidence = text[:240].replace("\n", " ")
                triples.append(
                    ExtractedTriple(
                        source_id=src.id,
                        source_name=src.display_name,
                        source_type=src.entity_type,
                        relationship=rel,
                        target_id=tgt.id,
                        target_name=tgt.display_name,
                        target_type=tgt.entity_type,
                        evidence=evidence,
                        confidence=0.58,
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page_number,
                        source_document=source_document,
                    )
                )
        return triples

    async def extract_chunk(
        self,
        chunk: Document,
        chunk_id: str,
        document_id: str,
        source_document: str,
    ) -> ExtractionResult:
        transformer = self._transformer()
        page_number = chunk.metadata.get("page_number")

        if transformer is None:
            triples = self._heuristic_extract(chunk, chunk_id, document_id, source_document)
            entities = [
                {
                    "id": t.source_id,
                    "name": t.source_name,
                    "type": t.source_type,
                }
                for t in triples
            ] + [
                {
                    "id": t.target_id,
                    "name": t.target_name,
                    "type": t.target_type,
                }
                for t in triples
            ]
            return ExtractionResult(triples=triples, entities=entities)

        try:
            docs = await transformer.aconvert_to_graph_documents([chunk])
        except Exception as exc:
            logger.warning("LLM extraction failed for %s: %s", chunk_id, exc)
            triples = self._heuristic_extract(chunk, chunk_id, document_id, source_document)
            return ExtractionResult(triples=triples)

        triples: list[ExtractedTriple] = []
        entities: list[dict[str, Any]] = []

        for gdoc in docs:
            node_map: dict[str, Any] = {}
            for node in gdoc.nodes:
                etype = _map_type(getattr(node, "type", "Topic") or "Topic")
                resolved = self.resolver.resolve(node.id, etype)
                node_map[node.id] = resolved
                entities.append(
                    {
                        "id": resolved.id,
                        "name": resolved.display_name,
                        "type": resolved.entity_type,
                        "aliases": resolved.aliases,
                    }
                )

            for rel in gdoc.relationships:
                src_raw = rel.source.id if hasattr(rel.source, "id") else str(rel.source)
                tgt_raw = rel.target.id if hasattr(rel.target, "id") else str(rel.target)
                src = node_map.get(src_raw) or self.resolver.resolve(
                    src_raw, _map_type(getattr(rel.source, "type", "Topic"))
                )
                tgt = node_map.get(tgt_raw) or self.resolver.resolve(
                    tgt_raw, _map_type(getattr(rel.target, "type", "Topic"))
                )
                rel_type = _map_rel(getattr(rel, "type", "RELATED_TO") or "RELATED_TO")
                evidence = chunk.page_content[:280].replace("\n", " ")
                triples.append(
                    ExtractedTriple(
                        source_id=src.id,
                        source_name=src.display_name,
                        source_type=src.entity_type,
                        relationship=rel_type,
                        target_id=tgt.id,
                        target_name=tgt.display_name,
                        target_type=tgt.entity_type,
                        evidence=evidence,
                        confidence=0.82,
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page_number,
                        source_document=source_document,
                    )
                )

        return ExtractionResult(triples=triples, entities=entities)
