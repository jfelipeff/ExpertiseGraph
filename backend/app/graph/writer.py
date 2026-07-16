from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.extraction.entity_resolution import ResolvedEntity
from app.extraction.graph_extractor import ExtractedTriple
from app.graph.neo4j_client import Neo4jClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphWriter:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def upsert_firm(self, firm: dict[str, Any]) -> None:
        self.client.run_write(
            """
            MERGE (f:Firm {id: $id})
            SET f.name = $name,
                f.description = $description,
                f.industry = $industry,
                f.notes = $notes,
                f.updated_at = $updated_at
            """,
            {**firm, "updated_at": _now()},
        )

    def upsert_document(self, doc: dict[str, Any]) -> None:
        self.client.run_write(
            """
            MERGE (d:Document {id: $id})
            SET d.filename = $filename,
                d.document_type = $document_type,
                d.chunking_strategy = $chunking_strategy,
                d.decision_rationale = $decision_rationale,
                d.decision_confidence = $decision_confidence,
                d.firm_id = $firm_id,
                d.created_at = coalesce(d.created_at, $created_at),
                d.updated_at = $created_at
            WITH d
            MATCH (f:Firm {id: $firm_id})
            MERGE (f)-[:OWNS]->(d)
            """,
            {**doc, "created_at": _now()},
        )

    def upsert_chunk(self, chunk: dict[str, Any]) -> None:
        self.client.run_write(
            """
            MERGE (c:Chunk {id: $id})
            SET c.text = $text,
                c.document_id = $document_id,
                c.page_number = $page_number,
                c.position = $position,
                c.embedding = $embedding,
                c.created_at = coalesce(c.created_at, $created_at)
            WITH c
            MATCH (d:Document {id: $document_id})
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            {**chunk, "created_at": _now()},
        )

    def upsert_entity(self, entity: ResolvedEntity, firm_id: str) -> None:
        self.client.run_write(
            """
            MERGE (e:Entity {id: $id})
            SET e.name = $name,
                e.canonical_name = $canonical_name,
                e.entity_type = $entity_type,
                e.aliases = $aliases,
                e.firm_id = $firm_id,
                e.updated_at = $updated_at
            SET e:Entity
            WITH e
            CALL apoc.create.addLabels(e, [$entity_type]) YIELD node
            RETURN node
            """,
            {
                "id": entity.id,
                "name": entity.display_name,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "aliases": entity.aliases,
                "firm_id": firm_id,
                "updated_at": _now(),
            },
        )

    def upsert_entity_safe(self, entity: ResolvedEntity, firm_id: str) -> None:
        """Same as upsert_entity but without APOC (works on vanilla Neo4j)."""
        # Dynamic label via separate query using a fixed set of labels
        self.client.run_write(
            """
            MERGE (e:Entity {id: $id})
            SET e.name = $name,
                e.canonical_name = $canonical_name,
                e.entity_type = $entity_type,
                e.aliases = $aliases,
                e.firm_id = $firm_id,
                e.updated_at = $updated_at
            """,
            {
                "id": entity.id,
                "name": entity.display_name,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "aliases": entity.aliases,
                "firm_id": firm_id,
                "updated_at": _now(),
            },
        )
        # Apply ontology label without APOC
        label = entity.entity_type
        allowed = {
            "Company", "Client", "Consultant", "Person", "Project", "Technology",
            "Industry", "Methodology", "Deliverable", "Initiative", "Capability",
            "Product", "Topic",
        }
        if label in allowed:
            self.client.run_write(
                f"""
                MATCH (e:Entity {{id: $id}})
                SET e:`{label}`
                """,
                {"id": entity.id},
            )

    def upsert_relationship(self, triple: ExtractedTriple) -> None:
        self.client.run_write(
            """
            MATCH (a:Entity {id: $source_id})
            MATCH (b:Entity {id: $target_id})
            MERGE (a)-[r:RELATED {rel_type: $relationship, chunk_id: $chunk_id}]->(b)
            SET r.type = $relationship,
                r.evidence = $evidence,
                r.confidence = $confidence,
                r.source_document = $source_document,
                r.document_id = $document_id,
                r.page_number = $page_number,
                r.chunk_id = $chunk_id,
                r.created_at = coalesce(r.created_at, $created_at),
                r.updated_at = $created_at
            WITH a, b, r
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (c)-[:MENTIONS]->(a)
            MERGE (c)-[:MENTIONS]->(b)
            """,
            {
                "source_id": triple.source_id,
                "target_id": triple.target_id,
                "relationship": triple.relationship,
                "evidence": triple.evidence,
                "confidence": triple.confidence,
                "source_document": triple.source_document,
                "document_id": triple.document_id,
                "page_number": triple.page_number,
                "chunk_id": triple.chunk_id,
                "created_at": _now(),
            },
        )

    def save_job(self, job: dict[str, Any]) -> None:
        import json

        # Nested maps are awkward in Neo4j props; store complex fields as JSON strings
        props = {
            "id": job["id"],
            "status": job.get("status"),
            "stage": job.get("stage"),
            "progress": job.get("progress"),
            "firm_id": job.get("firm_id"),
            "error": job.get("error"),
            "files": job.get("files"),
            "stats_json": json.dumps(job.get("stats") or {}),
            "decisions_json": json.dumps(job.get("decisions") or {}),
            "file_stages_json": json.dumps(job.get("file_stages") or {}),
            "updated_at": job.get("updated_at"),
        }
        self.client.run_write(
            """
            MERGE (j:IngestJob {id: $id})
            SET j += $props
            """,
            {"id": job["id"], "props": props},
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        rows = self.client.run(
            "MATCH (j:IngestJob {id: $id}) RETURN j {.*, id: j.id} AS job",
            {"id": job_id},
        )
        return rows[0]["job"] if rows else None
