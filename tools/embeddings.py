"""Embedding providers for corpus ingest / retrieval.

Default ``hash`` provider is deterministic and dependency-free (CI-safe).
Optional providers behind env:

- ``sentence_transformers`` — local models (requires optional install)
- ``openai`` — OpenAI-compatible embeddings API (requires API key)
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Literal, Protocol, Sequence

EmbeddingProviderName = Literal["hash", "sentence_transformers", "openai"]
DEFAULT_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0.0:
        return vector
    return [value / norm for value in vector]


class HashEmbeddingProvider:
    """Bag-of-words hashing trick → fixed-dim unit vectors (offline stub)."""

    name = "hash"

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        if dim < 8:
            raise ValueError("embedding dim must be >= 8")
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = _TOKEN_RE.findall((text or "").lower())
        if not tokens:
            vector[0] = 1.0
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            # Stable weight from remaining bytes.
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight
        return _l2_normalize(vector)


class SentenceTransformersProvider:
    name = "sentence_transformers"

    def __init__(self, model_name: str | None = None, dim: int | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional path
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "pip install sentence-transformers, or use CORPUS_EMBEDDING_PROVIDER=hash"
            ) from exc
        model_id = model_name or os.getenv(
            "CORPUS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._model = SentenceTransformer(model_id)
        probed = int(self._model.get_sentence_embedding_dimension())
        self.dim = dim or probed

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover
        vectors = self._model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [list(map(float, row)) for row in vectors]


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(self, model_name: str | None = None, dim: int = DEFAULT_DIM) -> None:
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY (or LLM_API_KEY) required for CORPUS_EMBEDDING_PROVIDER=openai"
            )
        self._api_key = api_key
        self._base_url = (
            os.getenv("CORPUS_EMBEDDING_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self._model = model_name or os.getenv(
            "CORPUS_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover
        import json
        import urllib.request

        payload = json.dumps({"model": self._model, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/embeddings",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        data = sorted(body.get("data") or [], key=lambda item: item.get("index", 0))
        vectors = [list(map(float, item["embedding"])) for item in data]
        if vectors:
            self.dim = len(vectors[0])
        return [_l2_normalize(vector) for vector in vectors]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right, strict=True)))


def get_embedding_provider(
    name: str | None = None,
    *,
    dim: int | None = None,
) -> EmbeddingProvider:
    provider = (name or os.getenv("CORPUS_EMBEDDING_PROVIDER") or "hash").strip().lower()
    if provider in {"hash", "stub", "deterministic"}:
        return HashEmbeddingProvider(dim=dim or DEFAULT_DIM)
    if provider in {"sentence_transformers", "st", "local"}:
        return SentenceTransformersProvider(dim=dim)
    if provider in {"openai", "api"}:
        return OpenAIEmbeddingProvider(dim=dim or DEFAULT_DIM)
    raise ValueError(f"Unknown CORPUS_EMBEDDING_PROVIDER: {provider!r}")
