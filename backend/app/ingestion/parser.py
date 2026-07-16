from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
from langchain_core.documents import Document


@dataclass
class ParsedPage:
    page_number: int
    text: str


@dataclass
class ParsedDocument:
    filename: str
    file_path: Path
    pages: list[ParsedPage] = field(default_factory=list)
    full_text: str = ""

    def to_langchain_pages(self) -> list[Document]:
        docs: list[Document] = []
        for page in self.pages:
            if not page.text.strip():
                continue
            docs.append(
                Document(
                    page_content=page.text,
                    metadata={
                        "page": page.page_number - 1,
                        "page_number": page.page_number,
                        "source": self.filename,
                    },
                )
            )
        return docs


def _clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(file_path: Path) -> ParsedDocument:
    doc = fitz.open(file_path)
    pages: list[ParsedPage] = []
    parts: list[str] = []
    for i, page in enumerate(doc):
        text = _clean_text(page.get_text("text"))
        pages.append(ParsedPage(page_number=i + 1, text=text))
        parts.append(text)
    doc.close()
    return ParsedDocument(
        filename=file_path.name,
        file_path=file_path,
        pages=pages,
        full_text="\n\n".join(parts),
    )


def parse_txt(file_path: Path) -> ParsedDocument:
    text = _clean_text(file_path.read_text(encoding="utf-8", errors="replace"))
    return ParsedDocument(
        filename=file_path.name,
        file_path=file_path,
        pages=[ParsedPage(page_number=1, text=text)],
        full_text=text,
    )


def parse_docx(file_path: Path) -> ParsedDocument:
    """Minimal DOCX text extraction without heavy deps (zip + XML)."""
    import zipfile
    from xml.etree import ElementTree as ET

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts: list[str] = []
    with zipfile.ZipFile(file_path) as zf:
        xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        for para in root.findall(".//w:p", ns):
            texts = [node.text or "" for node in para.findall(".//w:t", ns)]
            line = "".join(texts).strip()
            if line:
                parts.append(line)
    text = _clean_text("\n".join(parts))
    return ParsedDocument(
        filename=file_path.name,
        file_path=file_path,
        pages=[ParsedPage(page_number=1, text=text)],
        full_text=text,
    )


def parse_file(file_path: Path) -> ParsedDocument:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path)
    if suffix == ".txt":
        return parse_txt(file_path)
    if suffix == ".docx":
        return parse_docx(file_path)
    raise ValueError(f"Unsupported file type: {suffix}")
