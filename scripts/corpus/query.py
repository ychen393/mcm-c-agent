"""CLI: embed a query and print top-k corpus chunks.

Example:
  python -m scripts.corpus.query "transaction costs gold bitcoin sensitivity" --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.corpus_vector_store import get_vector_store  # noqa: E402
from tools.literature_corpus import retrieve_similar_chunks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query corpus embeddings")
    parser.add_argument("query", help="Natural-language query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--backend",
        choices=["auto", "memory", "json", "pgvector"],
        default="auto",
    )
    args = parser.parse_args(argv)

    store = get_vector_store(args.backend)
    hits = retrieve_similar_chunks(args.query, limit=args.limit, store=store)
    payload = [
        {
            "score": round(hit.score, 4),
            "source_id": hit.chunk.source_id,
            "chunk_id": hit.chunk.chunk_id,
            "title": hit.chunk.title,
            "citation_key": hit.chunk.citation_key,
            "text": hit.chunk.text[:400],
        }
        for hit in hits
    ]
    print(json.dumps({"backend": store.backend, "hits": payload}, indent=2))
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
