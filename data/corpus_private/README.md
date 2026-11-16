# Private corpus drop zone (gitignored)

Place **owner-provided** or **licensed** paper texts here for local ingest only.

## Rules

1. Do **not** commit award-paper PDFs or full texts to Git.
2. Every file must have a matching row in `knowledge/corpus_registry.csv`
   with `acquisition_method` of `owner_provided` or `licensed`, complete
   rights fields, and `review_status=approved` before full-text ingest.
3. Real MCM award papers may be copyrighted — obtain rights or keep
   metadata/link-only until the M1 Knowledge Ingestion Release Gate passes.
4. Prefer plain text (`.txt` / `.md`) or owner-extracted excerpts. PDF
   extraction is optional (`pip install -e ".[pdf]"`).

## Layout

```
data/corpus_private/
  README.md          # this file (tracked)
  .gitkeep
  my_paper_excerpt.txt   # gitignored via data/corpus_private/*
```

Register `local_path` as `data/corpus_private/<filename>` in the Corpus Registry,
then run:

```bash
python -m scripts.corpus.ingest --registry knowledge/corpus_registry.csv
```

See `docs/CORPUS_EMBEDDINGS.md`.
