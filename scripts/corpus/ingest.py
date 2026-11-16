"""CLI: ingest Corpus Registry texts into the vector store.

Examples:
  python -m scripts.corpus.ingest
  python -m scripts.corpus.ingest --backend json --clear
  python -m scripts.corpus.ingest --backend pgvector --clear
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.corpus_ingest import ingest_registry  # noqa: E402
from tools.corpus_vector_store import get_vector_store  # noqa: E402
from tools.embeddings import get_embedding_provider  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest corpus registry into embeddings")
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPO_ROOT / "knowledge" / "corpus_registry.csv",
        help="Path to corpus registry CSV",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "memory", "json", "pgvector"],
        default="json",
        help="Vector store backend (default: json under data/corpus_index/)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Embedding provider: hash | sentence_transformers | openai",
    )
    parser.add_argument("--clear", action="store_true", help="Clear store before ingest")
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        default=None,
        help="Limit ingest to one or more source_id values",
    )
    args = parser.parse_args(argv)

    embedder = get_embedding_provider(args.provider)
    store = get_vector_store(args.backend, dim=embedder.dim)
    report = ingest_registry(
        registry_path=args.registry,
        store=store,
        embedder=embedder,
        source_ids=args.source_ids,
        clear=args.clear,
        vector_backend=args.backend,
    )
    print(json.dumps(report.as_dict(), indent=2))
    if report.sources_ingested <= 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
