from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.graph.neo4j_client import Neo4jClient
from app.ingestion.embeddings import EmbeddingService
from app.llm import get_chat_llm, llm_configured

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    GraphRAG-style retrieval aligned with llm-graph-builder's graph_vector mode:
    1) vector search over Chunk embeddings
    2) expand to entities linked via MENTIONS and their RELATED edges
    3) also keyword/graph entity match for the question
    """

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client
        self.embedder = EmbeddingService()
        self.settings = get_settings()

    async def vector_search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        k = top_k or self.settings.vector_top_k
        embedding = await self.embedder.embed_query(query)
        try:
            rows = self.client.run(
                """
                CALL db.index.vector.queryNodes('chunk_embedding', $k, $embedding)
                YIELD node, score
                MATCH (d:Document)-[:HAS_CHUNK]->(node)
                RETURN node.id AS chunk_id,
                       node.text AS text,
                       node.page_number AS page_number,
                       d.filename AS document,
                       d.id AS document_id,
                       score
                ORDER BY score DESC
                """,
                {"k": k, "embedding": embedding},
            )
            if rows:
                return rows
        except Exception as exc:
            logger.info("Vector index query failed, falling back: %s", exc)

        chunks = self.client.run(
            """
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
            WHERE c.embedding IS NOT NULL
            RETURN c.id AS chunk_id, c.text AS text, c.page_number AS page_number,
                   c.embedding AS embedding, d.filename AS document, d.id AS document_id
            LIMIT 500
            """
        )
        scored = []
        for row in chunks:
            emb = row.get("embedding") or []
            score = _cosine(embedding, emb)
            scored.append({**row, "score": score, "embedding": None})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def expand_graph_from_chunks(self, chunk_ids: list[str], limit: int = 40) -> list[dict[str, Any]]:
        """Pull entities + relationships connected to retrieved chunks (vector→graph hop)."""
        if not chunk_ids:
            return []
        return self.client.run(
            """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE c.id IN $chunk_ids
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            RETURN DISTINCT e.id AS entity_id,
                   e.name AS entity_name,
                   e.entity_type AS entity_type,
                   collect(DISTINCT {
                       rel: coalesce(r.type, r.rel_type),
                       other: o.name,
                       other_type: o.entity_type,
                       evidence: r.evidence,
                       confidence: r.confidence,
                       source_document: r.source_document,
                       page_number: r.page_number
                   })[0..8] AS relationships
            LIMIT $limit
            """,
            {"chunk_ids": chunk_ids, "limit": limit},
        )

    def graph_search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        tokens = [t.lower() for t in query.replace("?", " ").split() if len(t) > 3]
        if not tokens:
            tokens = [query.lower()]
        return self.client.run(
            """
            MATCH (e:Entity)
            WHERE any(tok IN $tokens WHERE toLower(e.name) CONTAINS tok
                   OR toLower(e.canonical_name) CONTAINS tok
                   OR any(a IN coalesce(e.aliases, []) WHERE toLower(a) CONTAINS tok))
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            RETURN e.id AS entity_id,
                   e.name AS entity_name,
                   e.entity_type AS entity_type,
                   collect(DISTINCT {
                       rel: coalesce(r.type, r.rel_type),
                       other: o.name,
                       other_type: o.entity_type,
                       evidence: r.evidence,
                       confidence: r.confidence,
                       source_document: r.source_document,
                       page_number: r.page_number
                   })[0..8] AS relationships
            LIMIT $limit
            """,
            {"tokens": tokens, "limit": limit},
        )

    async def retrieve(self, query: str) -> dict[str, Any]:
        vector_hits = await self.vector_search(query)
        chunk_ids = [h["chunk_id"] for h in vector_hits if h.get("chunk_id")]
        graph_from_chunks = self.expand_graph_from_chunks(chunk_ids)
        graph_from_query = self.graph_search(query)

        # Merge entity rows by id
        by_id: dict[str, dict[str, Any]] = {}
        for row in graph_from_chunks + graph_from_query:
            eid = row.get("entity_id")
            if not eid:
                continue
            if eid not in by_id:
                by_id[eid] = row
            else:
                existing = by_id[eid].get("relationships") or []
                extra = row.get("relationships") or []
                seen = {(r.get("rel"), r.get("other")) for r in existing if r}
                for r in extra:
                    if not r or not r.get("other"):
                        continue
                    key = (r.get("rel"), r.get("other"))
                    if key not in seen:
                        existing.append(r)
                        seen.add(key)
                by_id[eid]["relationships"] = existing

        return {"vector": vector_hits, "graph": list(by_id.values())}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class ChatService:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client
        self.retriever = HybridRetriever(client)
        self.settings = get_settings()

    async def answer(self, question: str) -> dict[str, Any]:
        context = await self.retriever.retrieve(question)
        vector = context["vector"]
        graph = context["graph"]

        if not vector and not graph:
            return {
                "answer": "I don't have enough evidence in the knowledge base to answer that yet. Upload and ingest documents first.",
                "citations": [],
                "entities": [],
                "relationships": [],
                "evidence_used": False,
            }

        evidence_blocks = []
        citations = []
        for hit in vector:
            evidence_blocks.append(
                f"[DOC:{hit.get('document')} p.{hit.get('page_number')}] {hit.get('text', '')[:500]}"
            )
            citations.append(
                {
                    "document": hit.get("document"),
                    "page_number": hit.get("page_number"),
                    "chunk_id": hit.get("chunk_id"),
                    "score": hit.get("score"),
                    "snippet": (hit.get("text") or "")[:240],
                }
            )

        entities = []
        relationships = []
        for g in graph:
            entities.append(
                {
                    "id": g.get("entity_id"),
                    "name": g.get("entity_name"),
                    "type": g.get("entity_type"),
                }
            )
            for rel in g.get("relationships") or []:
                if not rel or not rel.get("other"):
                    continue
                relationships.append(
                    {
                        "from": g.get("entity_name"),
                        "type": rel.get("rel"),
                        "to": rel.get("other"),
                        "evidence": rel.get("evidence"),
                        "confidence": rel.get("confidence"),
                        "source_document": rel.get("source_document"),
                        "page_number": rel.get("page_number"),
                    }
                )
                evidence_blocks.append(
                    f"[GRAPH:{g.get('entity_name')}-{rel.get('rel')}->{rel.get('other')}] "
                    f"{rel.get('evidence') or ''} (conf={rel.get('confidence')})"
                )

        if not llm_configured():
            answer = (
                "Based on retrieved evidence:\n\n"
                + "\n".join(f"- {b[:220]}" for b in evidence_blocks[:6])
                + "\n\n(Set XAI_API_KEY / GROK_API_KEY for synthesized Grok answers.)"
            )
            return {
                "answer": answer,
                "citations": citations,
                "entities": entities,
                "relationships": relationships,
                "evidence_used": True,
            }

        llm = get_chat_llm(temperature=0)
        assert llm is not None
        prompt = f"""
You are an institutional memory assistant for a consulting firm.
Answer ONLY using the evidence below. If evidence is insufficient, say so.
Cite source documents and graph relationships explicitly.

Question: {question}

Evidence:
{chr(10).join(evidence_blocks[:20])}
"""
        response = await llm.ainvoke(prompt)
        answer = response.content if isinstance(response.content, str) else str(response.content)
        return {
            "answer": answer,
            "citations": citations,
            "entities": entities,
            "relationships": relationships,
            "evidence_used": True,
        }
