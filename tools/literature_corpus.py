"""Offline fixture corpus loader/search for Literature & Evidence (Phase 4+).

Deterministic keyword search remains the CI-safe baseline. Embedding retrieval
(hash stub by default) is available when a vector index has been ingested —
see tools/corpus_ingest.py and docs/CORPUS_EMBEDDINGS.md. Live remote retrieval
stays gated in agents/literature_evidence.py.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from tools.corpus_vector_store import RetrievedChunk, VectorStore, get_vector_store
from tools.embeddings import get_embedding_provider

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_PATH = (
    REPO_ROOT / "knowledge" / "fixture_corpus" / "2022_mcm_c_literature.json"
)


def _normalize_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def load_fixture_corpus(path: Path | None = None) -> dict[str, Any]:
    corpus_path = path or DEFAULT_CORPUS_PATH
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "sources" not in payload:
        raise ValueError(f"Invalid literature corpus at {corpus_path}")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"Literature corpus at {corpus_path} has no sources")
    return payload


@lru_cache(maxsize=4)
def cached_fixture_corpus(path_str: str | None = None) -> dict[str, Any]:
    path = Path(path_str) if path_str else DEFAULT_CORPUS_PATH
    return load_fixture_corpus(path)


def read_snippet_text(local_path: str | None, *, repo_root: Path | None = None) -> str | None:
    if not local_path:
        return None
    root = repo_root or REPO_ROOT
    path = Path(local_path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def score_source(source: dict[str, Any], query_tokens: set[str], rq_ids: set[str]) -> int:
    if not query_tokens and not rq_ids:
        return 0
    bag: set[str] = set()
    for key in ("title", "notes", "claim_summary"):
        value = source.get(key)
        if isinstance(value, str):
            bag |= _normalize_tokens(value)
    for key in ("keywords", "themes"):
        for item in source.get(key) or []:
            if isinstance(item, str):
                bag |= _normalize_tokens(item)
    score = len(bag & query_tokens)
    hints = {str(item) for item in (source.get("rq_hints") or [])}
    score += 3 * len(hints & rq_ids)
    return score


def search_fixture_sources(
    *,
    query_text: str = "",
    research_question_ids: list[str] | None = None,
    problem_id: str | None = None,
    limit: int = 8,
    corpus: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank fixture sources. Never invents entries outside the corpus."""
    data = corpus or load_fixture_corpus()
    sources = list(data.get("sources") or [])
    if problem_id:
        allowed = set(data.get("problem_ids") or [])
        # Corpus may be general; if problem_ids listed and do not match, still
        # allow search but prefer matching corpora callers filter upstream.
        _ = allowed
    query_tokens = _normalize_tokens(query_text)
    rq_ids = {item for item in (research_question_ids or []) if item}
    ranked: list[tuple[int, dict[str, Any]]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        score = score_source(source, query_tokens, rq_ids)
        if score <= 0 and (query_tokens or rq_ids):
            # Keep a weak thematic fallback for known 2022 C fixture sources so
            # empty overlaps still surface calendar/cost stubs when RQs exist.
            if rq_ids and source.get("source_id", "").startswith("fx_"):
                score = 1
            else:
                continue
        ranked.append((score, source))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("source_id") or "")))
    return [item for _, item in ranked[: max(1, limit)]]


def corpus_source_ids(corpus: dict[str, Any] | None = None) -> set[str]:
    data = corpus or load_fixture_corpus()
    return {
        str(source.get("source_id"))
        for source in (data.get("sources") or [])
        if isinstance(source, dict) and source.get("source_id")
    }


def embeddings_enabled() -> bool:
    """Embedding retrieval opt-in via env (default on when an index exists)."""
    raw = os.getenv("CORPUS_EMBEDDING_RETRIEVAL", "auto").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return True  # auto


def retrieve_similar_chunks(
    query_text: str,
    *,
    limit: int = 8,
    store: VectorStore | None = None,
    min_score: float = 0.05,
    provider_name: str | None = None,
) -> list[RetrievedChunk]:
    """Embed ``query_text`` and return top-k similar corpus chunks with scores.

    Returns an empty list when embeddings are disabled, the store is empty, or
    the query is blank. Never invents sources.
    """
    if not embeddings_enabled():
        return []
    query = (query_text or "").strip()
    if not query:
        return []
    vector_store = store
    if vector_store is None:
        try:
            vector_store = get_vector_store()
        except Exception:
            return []
    try:
        if vector_store.count() <= 0:
            return []
    except Exception:
        return []
    try:
        embedder = get_embedding_provider(provider_name)
        query_vec = embedder.embed([query])[0]
        hits = vector_store.search(query_vec, limit=limit)
    except Exception:
        return []
    return [hit for hit in hits if hit.score >= min_score]


def chunk_hit_to_source_dict(
    hit: RetrievedChunk,
    *,
    corpus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a retrieved chunk onto a fixture-like source dict for evidence cards."""
    data = corpus or load_fixture_corpus()
    by_id = {
        str(source.get("source_id")): source
        for source in (data.get("sources") or [])
        if isinstance(source, dict) and source.get("source_id")
    }
    chunk = hit.chunk
    base = dict(by_id.get(chunk.source_id) or {})
    acquisition = chunk.acquisition_method or base.get("acquisition_method") or "fixture_bundle"
    # Map registry acquisition kinds onto SourceMetadata literals.
    acquisition_map = {
        "fixture": "fixture_bundle",
        "owner_provided": "user_provided",
        "licensed": "institutional_subscription",
    }
    acquisition_method = acquisition_map.get(str(acquisition), acquisition)
    source_type = base.get("source_type") or (
        "fixture_stub" if acquisition_method == "fixture_bundle" else "user_provided"
    )
    return {
        **base,
        "source_id": chunk.source_id,
        "title": chunk.title or base.get("title") or chunk.source_id,
        "authors": chunk.authors or base.get("authors") or [],
        "year": chunk.year if chunk.year is not None else base.get("year"),
        "source_type": source_type,
        "local_path": chunk.local_path or base.get("local_path"),
        "snippet_file": base.get("snippet_file") or chunk.local_path,
        "acquisition_method": acquisition_method,
        "review_status": chunk.review_status or base.get("review_status") or "fixture",
        "license_or_rights": (chunk.metadata or {}).get("license_or_rights")
        or base.get("license_or_rights"),
        "publisher": (chunk.metadata or {}).get("publisher") or base.get("publisher"),
        "allowed_operations": (chunk.metadata or {}).get("allowed_operations")
        or base.get("allowed_operations")
        or ["metadata_index", "summarize", "excerpt_quote"],
        "claim_summary": base.get("claim_summary") or chunk.text[:400],
        "citation": base.get("citation")
        or {
            "citation_key": chunk.citation_key or f"Corpus_{chunk.source_id}",
            "citation_type": "fixture" if source_type == "fixture_stub" else "other",
            "bibtex_fields": {"title": chunk.title, "year": str(chunk.year or "")},
        },
        "method_notes": base.get("method_notes") or [],
        "themes": base.get("themes") or [],
        "keywords": base.get("keywords") or [],
        "rq_hints": base.get("rq_hints") or [],
        "_retrieval": {
            "backend": "embedding",
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "score": hit.score,
            "chunk_text": chunk.text,
        },
    }


def search_with_embeddings_fallback(
    *,
    query_text: str = "",
    research_question_ids: list[str] | None = None,
    problem_id: str | None = None,
    limit: int = 8,
    corpus: dict[str, Any] | None = None,
    store: VectorStore | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Prefer embedding hits when available; otherwise fixture keyword search.

    Returns ``(sources, backend_name)`` where backend_name is
    ``fixture_embeddings`` or ``fixture_corpus``.
    """
    data = corpus or load_fixture_corpus()
    hits = retrieve_similar_chunks(query_text, limit=limit, store=store)
    if hits:
        # Deduplicate by source_id, keep highest-scoring chunk per source.
        best: dict[str, RetrievedChunk] = {}
        for hit in hits:
            prior = best.get(hit.chunk.source_id)
            if prior is None or hit.score > prior.score:
                best[hit.chunk.source_id] = hit
        ranked = sorted(best.values(), key=lambda item: (-item.score, item.chunk.source_id))
        sources = [
            chunk_hit_to_source_dict(hit, corpus=data) for hit in ranked[: max(1, limit)]
        ]
        return sources, "fixture_embeddings"
    keyword = search_fixture_sources(
        query_text=query_text,
        research_question_ids=research_question_ids,
        problem_id=problem_id,
        limit=limit,
        corpus=data,
    )
    return keyword, "fixture_corpus"
