from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CORPORATE_SUFFIXES = re.compile(
    r"\b(inc\.?|incorporated|llc|ltd\.?|limited|corp\.?|corporation|co\.?|company|plc|gmbh|ag|sa|nv)\b\.?",
    re.IGNORECASE,
)


def normalize_entity_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", name or "").strip()
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = CORPORATE_SUFFIXES.sub("", text)
    text = re.sub(r"[^\w\s&\-+/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    # Common alias collapses
    aliases = {
        "open ai": "openai",
        "open-ai": "openai",
        "msft": "microsoft",
        "amazon web services": "aws",
        "gen ai": "generative ai",
        "genai": "generative ai",
    }
    return aliases.get(text, text)


@dataclass
class ResolvedEntity:
    canonical_name: str
    display_name: str
    entity_type: str
    aliases: list[str]
    id: str


def make_entity_id(entity_type: str, canonical_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", canonical_name).strip("-")
    return f"{entity_type.lower()}:{slug}"


class EntityResolver:
    """Merge near-duplicate entity mentions into canonical nodes with aliases."""

    def __init__(self) -> None:
        self._by_canonical: dict[str, ResolvedEntity] = {}

    def resolve(self, name: str, entity_type: str) -> ResolvedEntity:
        display = (name or "").strip()
        canonical = normalize_entity_name(display)
        if not canonical:
            canonical = "unknown"
            display = display or "Unknown"

        key = f"{entity_type.lower()}::{canonical}"
        existing = self._by_canonical.get(key)
        if existing:
            if display and display.lower() not in {a.lower() for a in existing.aliases}:
                if display.lower() != existing.display_name.lower():
                    existing.aliases.append(display)
            return existing

        entity = ResolvedEntity(
            canonical_name=canonical,
            display_name=display or canonical.title(),
            entity_type=entity_type,
            aliases=[display] if display else [],
            id=make_entity_id(entity_type, canonical),
        )
        self._by_canonical[key] = entity
        return entity

    def all_entities(self) -> list[ResolvedEntity]:
        return list(self._by_canonical.values())
