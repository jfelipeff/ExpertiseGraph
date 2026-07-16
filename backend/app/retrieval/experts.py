from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.graph.neo4j_client import Neo4jClient
from app.llm import get_chat_llm, llm_configured


class ExpertDiscovery:
    """Traverse Consultant → Projects → Clients → Topics and rank experts."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client
        self.settings = get_settings()

    def find_experts(self, question: str, limit: int = 8) -> dict[str, Any]:
        tokens = [t.lower() for t in question.replace("?", " ").split() if len(t) > 3]
        rows = self.client.run(
            """
            MATCH (person:Entity)
            WHERE person.entity_type IN ['Consultant', 'Person']
            OPTIONAL MATCH (person)-[r:RELATED]-(related:Entity)
            WHERE related.entity_type IN ['Project', 'Client', 'Topic', 'Technology', 'Industry', 'Capability', 'Methodology']
              AND (
                size($tokens) = 0 OR
                any(tok IN $tokens WHERE
                    toLower(related.name) CONTAINS tok OR
                    toLower(related.canonical_name) CONTAINS tok OR
                    toLower(coalesce(r.evidence, '')) CONTAINS tok
                )
              )
            WITH person,
                 collect(DISTINCT related) AS related_nodes,
                 collect(DISTINCT {
                     rel: coalesce(r.type, r.rel_type),
                     other: related.name,
                     other_type: related.entity_type,
                     evidence: r.evidence,
                     confidence: r.confidence,
                     source_document: r.source_document
                 }) AS evidence_links
            WHERE size(related_nodes) > 0 OR size($tokens) = 0
            OPTIONAL MATCH (person)-[:RELATED]-(proj:Entity {entity_type: 'Project'})
            OPTIONAL MATCH (person)-[:RELATED]-(client:Entity {entity_type: 'Client'})
            OPTIONAL MATCH (person)-[:RELATED]-(topic:Entity)
            WHERE topic.entity_type IN ['Topic', 'Technology', 'Industry', 'Capability']
            RETURN person.id AS id,
                   person.name AS name,
                   person.entity_type AS type,
                   size(related_nodes) AS relevance_degree,
                   collect(DISTINCT proj.name)[0..5] AS projects,
                   collect(DISTINCT client.name)[0..5] AS clients,
                   collect(DISTINCT topic.name)[0..8] AS topics,
                   evidence_links[0..6] AS evidence
            ORDER BY relevance_degree DESC, name ASC
            LIMIT $limit
            """,
            {"tokens": tokens, "limit": limit},
        )

        experts = []
        for row in rows:
            score = float(row.get("relevance_degree") or 0)
            reasoning = (
                f"{row['name']} connects to {int(score)} relevant nodes "
                f"across projects={row.get('projects')}, clients={row.get('clients')}, "
                f"topics={row.get('topics')}."
            )
            experts.append({**row, "score": score, "reasoning": reasoning})

        # If no Consultant/Person nodes, rank any entity heavily linked to query topics
        if not experts:
            fallback = self.client.run(
                """
                MATCH (e:Entity)-[r:RELATED]-(o:Entity)
                WHERE any(tok IN $tokens WHERE
                    toLower(e.name) CONTAINS tok OR toLower(o.name) CONTAINS tok
                    OR toLower(coalesce(r.evidence,'')) CONTAINS tok)
                RETURN e.id AS id, e.name AS name, e.entity_type AS type,
                       count(r) AS score,
                       collect(DISTINCT o.name)[0..8] AS topics,
                       collect(DISTINCT {
                         rel: coalesce(r.type, r.rel_type),
                         other: o.name,
                         evidence: r.evidence,
                         source_document: r.source_document
                       })[0..5] AS evidence
                ORDER BY score DESC
                LIMIT $limit
                """,
                {"tokens": tokens or [""], "limit": limit},
            )
            for row in fallback:
                experts.append(
                    {
                        **row,
                        "projects": [],
                        "clients": [],
                        "reasoning": (
                            f"{row['name']} ({row['type']}) appears in {row['score']} "
                            "evidence-linked relationships matching the query."
                        ),
                    }
                )

        narrative = None
        llm = get_chat_llm(temperature=0) if llm_configured() and experts else None
        if llm is not None:
            summary_input = "\n".join(
                f"- {e['name']} ({e['type']}): {e['reasoning']}" for e in experts[:5]
            )
            narrative = llm.invoke(
                f"Question: {question}\nRanked experts:\n{summary_input}\n"
                "Write a short recommendation of who to talk to and why, citing graph evidence."
            ).content

        return {"question": question, "experts": experts, "narrative": narrative}
