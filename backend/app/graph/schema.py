from app.graph.neo4j_client import Neo4jClient
from app.ontology import ALLOWED_NODE_TYPES


CONSTRAINTS = [
    "CREATE CONSTRAINT firm_id IF NOT EXISTS FOR (f:Firm) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT job_id IF NOT EXISTS FOR (j:IngestJob) REQUIRE j.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name)",
    "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
    "CREATE INDEX chunk_doc IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
    "CREATE INDEX rel_created IF NOT EXISTS FOR ()-[r:RELATED]-() ON (r.created_at)",
]


def init_schema(client: Neo4jClient) -> None:
    for stmt in CONSTRAINTS + INDEXES:
        try:
            client.run(stmt)
        except Exception:
            # Older Neo4j versions / already-exists race — continue.
            pass

    # Vector index for hybrid retrieval (Neo4j 5.11+)
    try:
        client.run(
            """
            CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {
              indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
              }
            }
            """
        )
    except Exception:
        pass

    # Ensure label documentation exists for ontology
    for label in ALLOWED_NODE_TYPES:
        client.run(
            """
            MERGE (t:OntologyType {name: $name})
            SET t.kind = 'node'
            """,
            {"name": label},
        )
