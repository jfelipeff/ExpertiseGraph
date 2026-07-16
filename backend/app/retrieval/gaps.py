from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.ontology import ALLOWED_NODE_TYPES


EXPECTED_NEIGHBOR_TYPES = {
    "Company": ["Product", "Client", "Technology", "Industry", "Initiative"],
    "Client": ["Project", "Industry", "Company"],
    "Consultant": ["Project", "Client", "Topic", "Capability", "Methodology"],
    "Person": ["Project", "Topic", "Company"],
    "Project": ["Client", "Methodology", "Technology", "Deliverable", "Consultant"],
    "Technology": ["Company", "Product", "Capability", "Topic"],
    "Industry": ["Client", "Company", "Topic"],
    "Methodology": ["Project", "Capability", "Deliverable"],
    "Topic": ["Technology", "Industry", "Capability"],
    "Product": ["Company", "Technology"],
    "Capability": ["Methodology", "Topic", "Consultant"],
    "Initiative": ["Company", "Project"],
    "Deliverable": ["Project", "Methodology"],
}


class KnowledgeGapEngine:
    """Identify sparse regions of the graph — 'what do we not know?'."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def detect(self, limit: int = 25) -> dict[str, Any]:
        entities = self.client.run(
            """
            MATCH (e:Entity)
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            WITH e,
                 count(r) AS degree,
                 collect(DISTINCT o.entity_type) AS neighbor_types,
                 collect(DISTINCT o.name)[0..8] AS known_neighbors
            RETURN e.id AS id,
                   e.name AS name,
                   e.entity_type AS type,
                   degree,
                   neighbor_types,
                   known_neighbors
            ORDER BY degree ASC, name ASC
            LIMIT 200
            """
        )

        gaps = []
        for e in entities:
            expected = EXPECTED_NEIGHBOR_TYPES.get(e["type"], ["Topic", "Company", "Project"])
            present = set(e.get("neighbor_types") or [])
            missing = [t for t in expected if t not in present]
            sparsity = 1.0 - (len(present) / max(len(expected), 1))
            if e["degree"] == 0 or missing:
                gaps.append(
                    {
                        "entity_id": e["id"],
                        "entity": e["name"],
                        "type": e["type"],
                        "degree": e["degree"],
                        "known": e.get("known_neighbors") or [],
                        "known_types": list(present),
                        "missing": missing,
                        "sparsity_score": round(sparsity, 3),
                        "question": (
                            f"What {', '.join(missing[:3]) or 'additional context'} "
                            f"do we know about {e['name']}?"
                        ),
                    }
                )

        gaps.sort(key=lambda g: (-g["sparsity_score"], g["degree"], g["entity"]))
        gaps = gaps[:limit]

        recent = self.client.run(
            """
            MATCH ()-[r:RELATED]->()
            WHERE r.created_at IS NOT NULL
            RETURN r.type AS type,
                   r.source_document AS source_document,
                   r.created_at AS created_at,
                   r.evidence AS evidence
            ORDER BY r.created_at DESC
            LIMIT 20
            """
        )

        type_coverage = self.client.run(
            """
            MATCH (e:Entity)
            RETURN e.entity_type AS type, count(*) AS count
            ORDER BY count DESC
            """
        )
        present_types = {row["type"] for row in type_coverage}
        missing_ontology = [t for t in ALLOWED_NODE_TYPES if t not in present_types and t not in ("Document", "Chunk")]

        return {
            "gaps": gaps,
            "recent_relationships": recent,
            "type_coverage": type_coverage,
            "missing_ontology_types": missing_ontology,
            "summary": (
                f"Found {len(gaps)} sparse entities. "
                f"Ontology types not yet observed: {', '.join(missing_ontology) or 'none'}."
            ),
        }
