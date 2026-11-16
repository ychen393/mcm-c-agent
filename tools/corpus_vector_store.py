"""Vector stores for corpus chunks: in-memory / JSON file / pgvector."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

from tools.embeddings import cosine_similarity

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON_INDEX = REPO_ROOT / "data" / "corpus_index" / "chunks.json"
DEFAULT_EMBEDDING_DIM = 384


@dataclass
class CorpusChunk:
    chunk_id: str
    source_id: str
    title: str
    text: str
    chunk_index: int
    embedding: list[float]
    citation_key: str | None = None
    local_path: str | None = None
    acquisition_method: str | None = None
    review_status: str | None = None
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CorpusChunk:
        return cls(
            chunk_id=str(payload["chunk_id"]),
            source_id=str(payload["source_id"]),
            title=str(payload.get("title") or payload["source_id"]),
            text=str(payload.get("text") or ""),
            chunk_index=int(payload.get("chunk_index") or 0),
            embedding=[float(value) for value in (payload.get("embedding") or [])],
            citation_key=payload.get("citation_key"),
            local_path=payload.get("local_path"),
            acquisition_method=payload.get("acquisition_method"),
            review_status=payload.get("review_status"),
            year=payload.get("year"),
            authors=list(payload.get("authors") or []),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: CorpusChunk
    score: float


class VectorStore(Protocol):
    backend: str

    def upsert(self, chunks: Sequence[CorpusChunk]) -> int:
        ...

    def search(
        self, query_embedding: Sequence[float], *, limit: int = 8
    ) -> list[RetrievedChunk]:
        ...

    def count(self) -> int:
        ...

    def clear(self) -> None:
        ...


class InMemoryVectorStore:
    backend = "memory"

    def __init__(self) -> None:
        self._chunks: dict[str, CorpusChunk] = {}

    def upsert(self, chunks: Sequence[CorpusChunk]) -> int:
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
        return len(chunks)

    def search(
        self, query_embedding: Sequence[float], *, limit: int = 8
    ) -> list[RetrievedChunk]:
        scored: list[RetrievedChunk] = []
        for chunk in self._chunks.values():
            score = cosine_similarity(query_embedding, chunk.embedding)
            scored.append(RetrievedChunk(chunk=chunk, score=score))
        scored.sort(key=lambda item: (-item.score, item.chunk.chunk_id))
        return scored[: max(1, limit)]

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()

    def all_chunks(self) -> list[CorpusChunk]:
        return list(self._chunks.values())


class JsonFileVectorStore(InMemoryVectorStore):
    """Persists chunks as JSON for local offline demos without Postgres."""

    backend = "json"

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.path = path or DEFAULT_JSON_INDEX
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("chunks") or []:
            if isinstance(item, dict):
                chunk = CorpusChunk.from_dict(item)
                self._chunks[chunk.chunk_id] = chunk

    def _save(self) -> None:
        payload = {
            "version": 1,
            "chunks": [chunk.to_dict() for chunk in self._chunks.values()],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def upsert(self, chunks: Sequence[CorpusChunk]) -> int:
        count = super().upsert(chunks)
        self._save()
        return count

    def clear(self) -> None:
        super().clear()
        self._save()


class PgVectorStore:
    """Postgres + pgvector backend (requires running docker compose postgres)."""

    backend = "pgvector"

    def __init__(
        self,
        database_url: str | None = None,
        *,
        dim: int = DEFAULT_EMBEDDING_DIM,
    ) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import Engine

        url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://mcm:mcm_dev_password@localhost:5432/mcm_research",
        )
        self.dim = dim
        # Short connect timeout so misconfigured local runs fail fast.
        connect_args: dict[str, Any] = {}
        if url.startswith("postgresql"):
            connect_args["connect_timeout"] = int(
                os.getenv("CORPUS_PG_CONNECT_TIMEOUT", "3")
            )
        self.engine: Engine = create_engine(
            url, pool_pre_ping=True, connect_args=connect_args
        )
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS corpus_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        source_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        body TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL DEFAULT 0,
                        embedding vector({dim}),
                        citation_key TEXT,
                        local_path TEXT,
                        acquisition_method TEXT,
                        review_status TEXT,
                        year INTEGER,
                        authors JSONB NOT NULL DEFAULT '[]'::jsonb,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS corpus_chunks_source_id_idx "
                    "ON corpus_chunks (source_id)"
                )
            )

    def upsert(self, chunks: Sequence[CorpusChunk]) -> int:
        from sqlalchemy import text

        if not chunks:
            return 0
        sql = text(
            """
            INSERT INTO corpus_chunks (
                chunk_id, source_id, title, body, chunk_index, embedding,
                citation_key, local_path, acquisition_method, review_status,
                year, authors, metadata
            ) VALUES (
                :chunk_id, :source_id, :title, :body, :chunk_index,
                CAST(:embedding AS vector), :citation_key, :local_path,
                :acquisition_method, :review_status, :year,
                CAST(:authors AS jsonb), CAST(:metadata AS jsonb)
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                source_id = EXCLUDED.source_id,
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                chunk_index = EXCLUDED.chunk_index,
                embedding = EXCLUDED.embedding,
                citation_key = EXCLUDED.citation_key,
                local_path = EXCLUDED.local_path,
                acquisition_method = EXCLUDED.acquisition_method,
                review_status = EXCLUDED.review_status,
                year = EXCLUDED.year,
                authors = EXCLUDED.authors,
                metadata = EXCLUDED.metadata
            """
        )
        with self.engine.begin() as conn:
            for chunk in chunks:
                if len(chunk.embedding) != self.dim:
                    raise ValueError(
                        f"chunk {chunk.chunk_id} dim {len(chunk.embedding)} "
                        f"!= store dim {self.dim}"
                    )
                conn.execute(
                    sql,
                    {
                        "chunk_id": chunk.chunk_id,
                        "source_id": chunk.source_id,
                        "title": chunk.title,
                        "body": chunk.text,
                        "chunk_index": chunk.chunk_index,
                        "embedding": "[" + ",".join(str(float(v)) for v in chunk.embedding) + "]",
                        "citation_key": chunk.citation_key,
                        "local_path": chunk.local_path,
                        "acquisition_method": chunk.acquisition_method,
                        "review_status": chunk.review_status,
                        "year": chunk.year,
                        "authors": json.dumps(chunk.authors),
                        "metadata": json.dumps(chunk.metadata),
                    },
                )
        return len(chunks)

    def search(
        self, query_embedding: Sequence[float], *, limit: int = 8
    ) -> list[RetrievedChunk]:
        from sqlalchemy import text

        if len(query_embedding) != self.dim:
            raise ValueError(
                f"query dim {len(query_embedding)} != store dim {self.dim}"
            )
        vector_literal = "[" + ",".join(str(float(v)) for v in query_embedding) + "]"
        sql = text(
            """
            SELECT chunk_id, source_id, title, body, chunk_index, embedding::text,
                   citation_key, local_path, acquisition_method, review_status,
                   year, authors, metadata,
                   1 - (embedding <=> CAST(:query AS vector)) AS score
            FROM corpus_chunks
            ORDER BY embedding <=> CAST(:query AS vector)
            LIMIT :limit
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(
                sql, {"query": vector_literal, "limit": max(1, limit)}
            ).mappings()
            results: list[RetrievedChunk] = []
            for row in rows:
                emb_raw = row["embedding"]
                if isinstance(emb_raw, str):
                    emb = [float(x) for x in emb_raw.strip("[]").split(",") if x]
                else:
                    emb = list(map(float, emb_raw))
                authors = row["authors"] or []
                if isinstance(authors, str):
                    authors = json.loads(authors)
                metadata = row["metadata"] or {}
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                chunk = CorpusChunk(
                    chunk_id=row["chunk_id"],
                    source_id=row["source_id"],
                    title=row["title"],
                    text=row["body"],
                    chunk_index=int(row["chunk_index"] or 0),
                    embedding=emb,
                    citation_key=row["citation_key"],
                    local_path=row["local_path"],
                    acquisition_method=row["acquisition_method"],
                    review_status=row["review_status"],
                    year=row["year"],
                    authors=list(authors),
                    metadata=dict(metadata),
                )
                results.append(
                    RetrievedChunk(chunk=chunk, score=float(row["score"] or 0.0))
                )
            return results

    def count(self) -> int:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM corpus_chunks")).scalar() or 0)

    def clear(self) -> None:
        from sqlalchemy import text

        with self.engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE corpus_chunks"))


def get_vector_store(
    backend: str | None = None,
    *,
    database_url: str | None = None,
    json_path: Path | None = None,
    dim: int = DEFAULT_EMBEDDING_DIM,
) -> VectorStore:
    name = (backend or os.getenv("CORPUS_VECTOR_BACKEND") or "auto").strip().lower()
    if name in {"memory", "mem"}:
        return InMemoryVectorStore()
    if name in {"json", "file"}:
        return JsonFileVectorStore(json_path)
    if name in {"pgvector", "postgres", "pg"}:
        return PgVectorStore(database_url=database_url, dim=dim)
    if name == "auto":
        # Prefer a persisted JSON index when present. Do not probe Postgres in
        # auto mode (keeps CI/offline E2E fast). Use CORPUS_VECTOR_BACKEND=pgvector
        # explicitly after `docker compose up -d postgres`.
        path = json_path or DEFAULT_JSON_INDEX
        if path.is_file():
            return JsonFileVectorStore(path)
        return InMemoryVectorStore()
    raise ValueError(f"Unknown CORPUS_VECTOR_BACKEND: {name!r}")
