from __future__ import annotations

import logging
import math
import hashlib
from typing import Sequence

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Deterministic local embeddings (no external API required for Grok-only setups)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._dim = 1536

    @property
    def available(self) -> bool:
        return True

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._hash_embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._hash_embed(text)

    def _hash_embed(self, text: str, dim: int | None = None) -> list[float]:
        dim = dim or self._dim
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vals: list[float] = []
        seed = digest
        while len(vals) < dim:
            seed = hashlib.sha256(seed).digest()
            for b in seed:
                vals.append((b / 255.0) * 2 - 1)
                if len(vals) >= dim:
                    break
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]
