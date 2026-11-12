"""Offline fixture corpus loader/search for Literature & Evidence (Phase 4).

Deterministic and network-free. Live retrieval is intentionally not implemented
here — see agents/literature_evidence.py for the gated stub.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

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
