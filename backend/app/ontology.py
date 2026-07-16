"""Ontology-driven node and relationship types for consulting institutional memory."""

# Extraction labels only (Document/Chunk are structural, not LLM-extracted)
ALLOWED_NODE_TYPES = [
    "Company",
    "Client",
    "Consultant",
    "Person",
    "Project",
    "Technology",
    "Industry",
    "Methodology",
    "Deliverable",
    "Initiative",
    "Capability",
    "Product",
    "Topic",
]

ALLOWED_RELATIONSHIPS = [
    "WORKED_ON",
    "USED",
    "AUTHORED",
    "IMPLEMENTED",
    "FOR_CLIENT",
    "RELATED_TO",
    "EXPERT_IN",
    "DEPENDS_ON",
    "PARTNERS_WITH",
    "MENTIONS",
    "PART_OF",
    "USES_METHODOLOGY",
]

DOCUMENT_TYPES = [
    "Meeting Notes",
    "Consulting Deliverable",
    "Methodology",
    "Financial Report",
    "Research Report",
    "Contract",
    "Strategy Presentation",
    "White Paper",
    "Other",
]

# Mirrors llm-graph-builder ADDITIONAL_INSTRUCTIONS + consulting constraints
ADDITIONAL_INSTRUCTIONS = """
Your goal is to identify and categorize entities while ensuring that specific data
types such as dates, numbers, revenues, and other non-entity information are not extracted as separate nodes.
Instead, treat these as properties associated with the relevant entities.
Only create nodes of these types: {node_types}.
Only create relationships of these types: {rel_types}.
Prefer concrete named entities (people, firms, methods, technologies, industries, projects, clients).
Do not invent facts that are not supported by the text.
""".strip()

EXTRACTION_PROMPT = ADDITIONAL_INSTRUCTIONS
