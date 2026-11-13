"""Ingest registry-approved texts: chunk → embed → vector store."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from tools.corpus_registry import (
    DEFAULT_REGISTRY_PATH,
    CorpusRegistryRow,
    assert_ingest_allowed,
    load_corpus_registry,
    resolve_local_text_path,
)
from tools.corpus_vector_store import (
    CorpusChunk,
    InMemoryVectorStore,
    JsonFileVectorStore,
    VectorStore,
    get_vector_store,
)
from tools.embeddings import EmbeddingProvider, get_embedding_provider
from tools.literature_corpus import load_fixture_corpus

REPO_ROOT = Path(__file__).resolve().parents[1]
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class IngestReport:
    sources_considered: int
    sources_ingested: int
    chunks_upserted: int
    skipped: list[str]
    backend: str
    embedding_provider: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sources_considered": self.sources_considered,
            "sources_ingested": self.sources_ingested,
            "chunks_upserted": self.chunks_upserted,
            "skipped": list(self.skipped),
            "backend": self.backend,
            "embedding_provider": self.embedding_provider,
        }


def chunk_text(
    text: str,
    *,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> list[str]:
    """Simple character-window chunker with overlap (offline-friendly)."""
    cleaned = _WHITESPACE_RE.sub(" ", (text or "").strip())
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = max(0, min(chunk_overlap, chunk_size - 1))
    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(length, start + chunk_size)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(0, end - overlap)
    return chunks


def read_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".csv", ".json"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            import fitz  # pymupdf
        except ImportError as exc:
            raise RuntimeError(
                f"PDF ingest requires pymupdf (pip install -e '.[pdf]'): {path}"
            ) from exc
        doc = fitz.open(path)
        try:
            return "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()
    raise ValueError(f"Unsupported corpus file type: {path.suffix}")


def _citation_key_for(row: CorpusRegistryRow, fixture_meta: dict[str, Any] | None) -> str:
    if fixture_meta:
        citation = fixture_meta.get("citation") or {}
        if isinstance(citation, dict) and citation.get("citation_key"):
            return str(citation["citation_key"])
    return f"Corpus_{row.source_id}"


def _authors_for(row: CorpusRegistryRow, fixture_meta: dict[str, Any] | None) -> list[str]:
    if fixture_meta and fixture_meta.get("authors"):
        return [str(item) for item in fixture_meta["authors"]]
    if row.author_or_org:
        return [row.author_or_org]
    return []


def build_chunks_for_row(
    row: CorpusRegistryRow,
    text: str,
    *,
    embedder: EmbeddingProvider,
    fixture_meta: dict[str, Any] | None = None,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> list[CorpusChunk]:
    assert_ingest_allowed(row)
    pieces = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not pieces:
        return []
    vectors = embedder.embed(pieces)
    citation_key = _citation_key_for(row, fixture_meta)
    authors = _authors_for(row, fixture_meta)
    chunks: list[CorpusChunk] = []
    for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
        chunks.append(
            CorpusChunk(
                chunk_id=f"{row.source_id}__{index}",
                source_id=row.source_id,
                title=row.title,
                text=piece,
                chunk_index=index,
                embedding=vector,
                citation_key=citation_key,
                local_path=row.local_path,
                acquisition_method=row.acquisition_method,
                review_status=row.review_status,
                year=row.year,
                authors=authors,
                metadata={
                    "publisher": row.publisher,
                    "license_or_rights": row.license_or_rights_statement,
                    "allowed_operations": list(row.allowed_operations),
                },
            )
        )
    return chunks


def _fixture_meta_index() -> dict[str, dict[str, Any]]:
    try:
        corpus = load_fixture_corpus()
    except Exception:
        return {}
    return {
        str(source["source_id"]): source
        for source in (corpus.get("sources") or [])
        if isinstance(source, dict) and source.get("source_id")
    }


def ingest_registry(
    *,
    registry_path: Path | None = None,
    store: VectorStore | None = None,
    embedder: EmbeddingProvider | None = None,
    source_ids: Sequence[str] | None = None,
    clear: bool = False,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    repo_root: Path | None = None,
    vector_backend: str | None = None,
) -> IngestReport:
    """Ingest all gate-passing registry rows that have readable local text."""
    root = repo_root or REPO_ROOT
    rows = load_corpus_registry(registry_path or DEFAULT_REGISTRY_PATH)
    if source_ids:
        wanted = {item.lower() for item in source_ids}
        rows = [row for row in rows if row.source_id in wanted]
    provider = embedder or get_embedding_provider()
    vector_store = store or get_vector_store(
        vector_backend, dim=getattr(provider, "dim", 384)
    )
    if clear:
        vector_store.clear()
    fixture_index = _fixture_meta_index()
    skipped: list[str] = []
    upserted = 0
    ingested_sources = 0
    for row in rows:
        path = resolve_local_text_path(row, repo_root=root)
        if path is None:
            skipped.append(f"{row.source_id}: local_path missing or not found")
            continue
        try:
            assert_ingest_allowed(row)
            text = read_source_text(path)
            chunks = build_chunks_for_row(
                row,
                text,
                embedder=provider,
                fixture_meta=fixture_index.get(row.source_id),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        except Exception as exc:  # noqa: BLE001 — collect per-source failures
            skipped.append(f"{row.source_id}: {exc}")
            continue
        if not chunks:
            skipped.append(f"{row.source_id}: empty text after chunking")
            continue
        upserted += vector_store.upsert(chunks)
        ingested_sources += 1
    return IngestReport(
        sources_considered=len(rows),
        sources_ingested=ingested_sources,
        chunks_upserted=upserted,
        skipped=skipped,
        backend=getattr(vector_store, "backend", "unknown"),
        embedding_provider=getattr(provider, "name", "unknown"),
    )


def ingest_fixture_corpus_for_tests(
    *,
    store: VectorStore | None = None,
    embedder: EmbeddingProvider | None = None,
) -> tuple[VectorStore, IngestReport]:
    """Convenience: ingest fixture registry rows into memory (CI)."""
    provider = embedder or get_embedding_provider("hash")
    vector_store: VectorStore = store or InMemoryVectorStore()
    report = ingest_registry(
        store=vector_store,
        embedder=provider,
        clear=True,
        vector_backend="memory",
    )
    # Ensure JSON path is not required.
    if isinstance(vector_store, JsonFileVectorStore):
        pass
    return vector_store, report
