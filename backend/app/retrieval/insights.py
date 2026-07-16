from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.llm import get_chat_llm, llm_configured


class InsightService:
    """Summarize ingested corpus and propose GraphRAG-ready questions."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def build(self) -> dict[str, Any]:
        docs = self.client.run(
            """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            RETURN d.filename AS filename,
                   d.document_type AS document_type,
                   d.chunking_strategy AS chunking_strategy,
                   d.decision_rationale AS decision_rationale,
                   count(c) AS chunks
            ORDER BY d.filename
            """
        )
        top_entities = self.client.run(
            """
            MATCH (e:Entity)
            OPTIONAL MATCH (e)-[r:RELATED]-()
            RETURN e.name AS name, e.entity_type AS type, count(r) AS degree
            ORDER BY degree DESC, name ASC
            LIMIT 12
            """
        )
        top_rels = self.client.run(
            """
            MATCH (a:Entity)-[r:RELATED]->(b:Entity)
            RETURN a.name AS source,
                   coalesce(r.type, r.rel_type) AS type,
                   b.name AS target,
                   r.evidence AS evidence
            ORDER BY coalesce(r.confidence, 0) DESC
            LIMIT 8
            """
        )
        stats = self.client.run(
            """
            OPTIONAL MATCH (e:Entity) WITH count(e) AS entities
            OPTIONAL MATCH ()-[r:RELATED]->() WITH entities, count(r) AS relationships
            OPTIONAL MATCH (c:Chunk) WITH entities, relationships, count(c) AS chunks
            OPTIONAL MATCH (d:Document)
            RETURN entities, relationships, chunks, count(d) AS documents
            """
        )
        summary_stats = stats[0] if stats else {}

        company_names = [e["name"] for e in top_entities if e.get("type") == "Company"][:4]
        industries = [e["name"] for e in top_entities if e.get("type") == "Industry"][:4]
        technologies = [e["name"] for e in top_entities if e.get("type") == "Technology"][:4]
        topics = [e["name"] for e in top_entities if e.get("type") == "Topic"][:4]

        doc_titles = [d.get("filename", "document") for d in docs]
        summary = self._compose_summary(docs, summary_stats)
        questions = self._compose_questions(company_names, industries, technologies, topics, doc_titles)
        expert_prompts = self._compose_expert_prompts(company_names, industries, technologies, topics)

        if llm_configured() and (docs or top_entities):
            try:
                llm_bits = self._llm_enrich(summary, questions, top_entities, top_rels)
                if llm_bits.get("analysis"):
                    summary = llm_bits["analysis"]
                if llm_bits.get("questions"):
                    questions = llm_bits["questions"]
            except Exception:
                pass

        return {
            "summary": summary,
            "analysis": summary,  # backward compatible
            "documents": docs,
            "stats": summary_stats,
            "spotlight_entities": top_entities,
            "spotlight_relationships": top_rels,
            "suggested_questions": questions,
            "expert_prompts": expert_prompts,
            "llm_provider": "grok" if llm_configured() else "heuristic",
        }

    def _compose_summary(
        self,
        docs: list[dict[str, Any]],
        stats: dict[str, Any],
    ) -> str:
        if not docs:
            return "No documents have been analyzed yet. Ingest a corpus to explore institutional memory."
        n = stats.get("documents", len(docs))
        types = sorted({d.get("document_type") or "Unknown" for d in docs})
        return (
            f"Processed {n} document(s) into a searchable knowledge graph "
            f"({stats.get('entities', 0)} entities · {stats.get('relationships', 0)} relationships · "
            f"{stats.get('chunks', 0)} chunks). Primary document types: {', '.join(types)}."
        )

    def _compose_questions(
        self,
        companies: list[str],
        industries: list[str],
        technologies: list[str],
        topics: list[str],
        docs: list[str],
    ) -> list[dict[str, str]]:
        c = companies[0] if companies else "the leading companies"
        c2 = companies[1] if len(companies) > 1 else "their competitors"
        ind = industries[0] if industries else "emerging arenas"
        tech = technologies[0] if technologies else "AI"
        topic = topics[0] if topics else "competition dynamics"
        doc = docs[0] if docs else "the ingested research"

        return [
            {
                "id": "q1",
                "question": f"Which companies are most connected to {ind}, and what relationships explain that?",
                "why": "Surfaces company–industry structure from the graph.",
            },
            {
                "id": "q2",
                "question": f"How do {c} and {c2} relate through technologies, partnerships, or competitive arenas?",
                "why": "Compares entities using hybrid vector + graph evidence.",
            },
            {
                "id": "q3",
                "question": f"What does the corpus say about {tech} and where does it show up across documents?",
                "why": "Cross-document theme with citations.",
            },
            {
                "id": "q4",
                "question": f"What are the key claims in {doc} about {topic}?",
                "why": "Grounded reading of a specific source.",
            },
            {
                "id": "q5",
                "question": "Which relationships in the graph have the strongest evidence, and what do they imply?",
                "why": "Prioritizes high-provenance edges.",
            },
        ]

    def _compose_expert_prompts(
        self,
        companies: list[str],
        industries: list[str],
        technologies: list[str],
        topics: list[str],
    ) -> list[dict[str, str]]:
        ind = industries[0] if industries else "digital transformation"
        tech = technologies[0] if technologies else "AI strategy"
        company = companies[0] if companies else "arena leaders"
        return [
            {
                "id": "e1",
                "question": f"Who should I talk to about {tech} for {ind}?",
                "why": "Classic consulting expert routing.",
            },
            {
                "id": "e2",
                "question": f"Which people or entities appear most often around {company}?",
                "why": "Finds concentrated expertise neighborhoods.",
            },
            {
                "id": "e3",
                "question": f"Who has cross-cutting experience across {ind} and {tech}?",
                "why": "Multi-hop consultant → topic → industry pattern.",
            },
        ]

    def _llm_enrich(
        self,
        analysis: str,
        questions: list[dict[str, str]],
        entities: list[dict[str, Any]],
        rels: list[dict[str, Any]],
    ) -> dict[str, Any]:
        import json
        import re

        llm = get_chat_llm(temperature=0.3)
        if llm is None:
            return {}
        prompt = f"""
You help consultants explore an institutional knowledge graph.
Given this draft analysis and graph spotlight, rewrite a crisp 2-3 sentence analysis
and 5 insightful questions a partner would ask. Questions must be answerable from
documents + graph relationships (not generic trivia).

Draft analysis:
{analysis}

Entities: {entities[:10]}
Relationships: {rels[:8]}
Draft questions: {[q['question'] for q in questions]}

Return ONLY JSON:
{{"analysis":"...","questions":[{{"question":"...","why":"..."}}]}}
"""
        content = llm.invoke(prompt).content
        text = content if isinstance(content, str) else str(content)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        data = json.loads(match.group(0))
        qs = []
        for i, q in enumerate(data.get("questions") or []):
            qs.append(
                {
                    "id": f"q{i+1}",
                    "question": q.get("question") or "",
                    "why": q.get("why") or "",
                }
            )
        return {"analysis": data.get("analysis"), "questions": [q for q in qs if q["question"]]}
