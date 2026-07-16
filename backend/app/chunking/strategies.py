from __future__ import annotations

import re
from typing import Callable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter

from app.agents.document_intelligence import ChunkStrategy, DocumentIntelligenceDecision
from app.config import get_settings


def _token_splitter(chunk_size: int | None = None, overlap: int | None = None) -> TokenTextSplitter:
    settings = get_settings()
    return TokenTextSplitter(
        chunk_size=chunk_size or settings.token_chunk_size,
        chunk_overlap=overlap if overlap is not None else settings.chunk_overlap,
        encoding_name="gpt2",
    )


def _semantic_chunks(pages: list[Document]) -> list[Document]:
    """Paragraph / thought-boundary aware splitting."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
        length_function=len,
    )
    return _split_preserving_pages(pages, splitter.split_documents)


def _section_chunks(pages: list[Document]) -> list[Document]:
    """Split on markdown-ish / ALL-CAPS / numbered headings when possible."""
    heading = re.compile(r"(?m)^(#{1,3}\s+.+|[A-Z][A-Z0-9 ,\-/]{8,}|^\d+\.\s+[A-Z].+)$")
    chunks: list[Document] = []
    for page in pages:
        text = page.page_content
        parts = heading.split(text)
        if len(parts) <= 1:
            chunks.extend(_token_splitter().split_documents([page]))
            continue
        buffer = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(buffer) + len(part) < 1800:
                buffer = f"{buffer}\n\n{part}".strip()
            else:
                if buffer:
                    chunks.append(
                        Document(page_content=buffer, metadata={**page.metadata})
                    )
                buffer = part
        if buffer:
            chunks.append(Document(page_content=buffer, metadata={**page.metadata}))
    return chunks


def _hierarchical_chunks(pages: list[Document]) -> list[Document]:
    """Coarse parent sections then finer child tokens."""
    coarse = RecursiveCharacterTextSplitter(
        chunk_size=2400,
        chunk_overlap=200,
        separators=["\n\n\n", "\n\n", "\n", " "],
    ).split_documents(pages)
    fine: list[Document] = []
    child = _token_splitter(chunk_size=350, overlap=40)
    for parent in coarse:
        children = child.split_documents([parent])
        for idx, child_doc in enumerate(children):
            meta = {
                **parent.metadata,
                **child_doc.metadata,
                "parent_preview": parent.page_content[:180],
                "hierarchy_level": "child",
                "child_index": idx,
            }
            fine.append(Document(page_content=child_doc.page_content, metadata=meta))
    return fine


def _clause_chunks(pages: list[Document]) -> list[Document]:
    clause_re = re.compile(
        r"(?m)((?:Article|Section|Clause)\s+[\dA-Z\.]+[:.\s].*?)(?=(?:Article|Section|Clause)\s+[\dA-Z\.]+[:.\s]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    chunks: list[Document] = []
    for page in pages:
        matches = clause_re.findall(page.page_content)
        if not matches:
            chunks.extend(_token_splitter().split_documents([page]))
            continue
        for clause in matches:
            clause = clause.strip()
            if len(clause) < 40:
                continue
            chunks.append(Document(page_content=clause, metadata={**page.metadata, "unit": "clause"}))
    return chunks


def _split_preserving_pages(
    pages: list[Document],
    split_fn: Callable[[list[Document]], list[Document]],
) -> list[Document]:
    out: list[Document] = []
    for page in pages:
        page_number = page.metadata.get("page_number") or (int(page.metadata.get("page", 0)) + 1)
        for chunk in split_fn([page]):
            meta = {**chunk.metadata, "page_number": page_number}
            out.append(Document(page_content=chunk.page_content, metadata=meta))
    return out


STRATEGY_MAP: dict[ChunkStrategy, Callable[[list[Document]], list[Document]]] = {
    "semantic": _semantic_chunks,
    "hierarchical": _hierarchical_chunks,
    "section": _section_chunks,
    "clause": _clause_chunks,
    "token": lambda pages: _split_preserving_pages(pages, _token_splitter().split_documents),
}


def chunk_document(
    pages: list[Document],
    decision: DocumentIntelligenceDecision,
) -> list[Document]:
    settings = get_settings()
    strategy = decision.chunking_strategy
    fn = STRATEGY_MAP.get(strategy, STRATEGY_MAP["token"])
    chunks = fn(pages)
    if len(chunks) > settings.max_chunks_per_doc:
        chunks = chunks[: settings.max_chunks_per_doc]
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["chunking_strategy"] = strategy
        chunk.metadata["document_type"] = decision.document_type
    return chunks
