from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient


class GraphExplorer:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def full_graph(self, limit_nodes: int = 300, limit_edges: int = 600) -> dict[str, Any]:
        nodes = self.client.run(
            """
            MATCH (e:Entity)
            RETURN e.id AS id,
                   e.name AS label,
                   e.entity_type AS type,
                   e.aliases AS aliases,
                   e.canonical_name AS canonical_name
            LIMIT $limit
            """,
            {"limit": limit_nodes},
        )
        edges = self.client.run(
            """
            MATCH (a:Entity)-[r:RELATED]->(b:Entity)
            RETURN a.id AS source,
                   b.id AS target,
                   coalesce(r.type, r.rel_type) AS type,
                   r.evidence AS evidence,
                   r.confidence AS confidence,
                   r.source_document AS source_document,
                   r.page_number AS page_number,
                   r.chunk_id AS chunk_id,
                   elementId(r) AS id
            LIMIT $limit
            """,
            {"limit": limit_edges},
        )
        docs = self.client.run(
            """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            RETURN d.id AS id,
                   d.filename AS label,
                   'Document' AS type,
                   d.document_type AS document_type,
                   d.chunking_strategy AS chunking_strategy,
                   d.decision_rationale AS decision_rationale,
                   count(c) AS chunk_count
            """
        )
        return {"nodes": nodes + docs, "edges": edges}

    def search_nodes(self, q: str, limit: int = 30) -> list[dict[str, Any]]:
        return self.client.run(
            """
            MATCH (e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($q)
               OR toLower(e.canonical_name) CONTAINS toLower($q)
               OR any(a IN coalesce(e.aliases, []) WHERE toLower(a) CONTAINS toLower($q))
            RETURN e.id AS id, e.name AS label, e.entity_type AS type, e.aliases AS aliases
            LIMIT $limit
            """,
            {"q": q, "limit": limit},
        )

    def node_detail(self, node_id: str) -> dict[str, Any]:
        rows = self.client.run(
            """
            MATCH (e:Entity {id: $id})
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            RETURN e {.*, id: e.id} AS node,
                   collect({
                       direction: CASE WHEN startNode(r) = e THEN 'out' ELSE 'in' END,
                       type: coalesce(r.type, r.rel_type),
                       other_id: o.id,
                       other_name: o.name,
                       other_type: o.entity_type,
                       evidence: r.evidence,
                       confidence: r.confidence,
                       source_document: r.source_document,
                       page_number: r.page_number,
                       chunk_id: r.chunk_id
                   }) AS relationships
            """,
            {"id": node_id},
        )
        return rows[0] if rows else {}

    def temporal_changes(self, days: int = 30) -> dict[str, Any]:
        rels = self.client.run(
            """
            MATCH (a:Entity)-[r:RELATED]->(b:Entity)
            WHERE r.created_at IS NOT NULL
            RETURN a.name AS source,
                   coalesce(r.type, r.rel_type) AS type,
                   b.name AS target,
                   r.created_at AS created_at,
                   r.source_document AS source_document,
                   r.evidence AS evidence
            ORDER BY r.created_at DESC
            LIMIT 50
            """
        )
        docs = self.client.run(
            """
            MATCH (d:Document)
            RETURN d.filename AS filename,
                   d.document_type AS document_type,
                   d.created_at AS created_at,
                   d.chunking_strategy AS chunking_strategy
            ORDER BY d.created_at DESC
            LIMIT 20
            """
        )
        return {"relationships": rels, "documents": docs, "window_days": days}
