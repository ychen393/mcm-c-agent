CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Literature corpus chunk embeddings (created/ensured also by tools.corpus_vector_store).
CREATE TABLE IF NOT EXISTS corpus_chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    embedding vector(384),
    citation_key TEXT,
    local_path TEXT,
    acquisition_method TEXT,
    review_status TEXT,
    year INTEGER,
    authors JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS corpus_chunks_source_id_idx ON corpus_chunks (source_id);
