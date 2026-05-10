"""Embedding helpers.

Uses OpenAI embeddings when configured, otherwise falls back to a hashing
trick so the project stays bootable without an API key. The fallback isn't
semantically useful, but it lets local tests run end-to-end.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.cve import EMBEDDING_DIM
from app.utils.logger import get_logger

logger = get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.llm_enabled:
        return [_hash_embed(t) for t in texts]

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=list(texts),
    )
    return [item.embedding for item in response.data]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def _hash_embed(text: str) -> list[float]:
    """Deterministic, low-quality fallback embedding.

    Hash the text into 1536 pseudo-random floats in [-1, 1]. Useless for real
    semantic search, but enough to exercise the pgvector storage/query path
    in tests.
    """
    digest = hashlib.sha512(text.encode("utf-8")).digest()
    repeats = (EMBEDDING_DIM // len(digest)) + 1
    raw = (digest * repeats)[:EMBEDDING_DIM]
    return [(b / 127.5) - 1.0 for b in raw]
