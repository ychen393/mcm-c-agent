# Corpus Registry, Ingest & Embedding Retrieval

**Status:** Draft slice on top of Phase 4 Literature & Evidence.  
**Constraint:** Do not scrape or commit pirated MCM award PDFs. M1 Knowledge
Ingestion Release Gate (PRD §23.3) must pass before bulk ingest of real award
papers.

## What this delivers

1. **Corpus Registry** — `knowledge/corpus_registry.csv` (from
   `CORPUS_REGISTRY_TEMPLATE.csv`) with provenance + rights fields.
2. **Ingest pipeline** — chunk → embed → store (`tools/corpus_ingest.py`).
3. **Seed corpus** — expanded synthetic *excellent-paper-style* fixtures under
   `knowledge/fixture_corpus/` (clearly labeled; not real award papers).
4. **Private drop zone** — gitignored `data/corpus_private/` for owner-provided
   / licensed texts after registry approval.
5. **Query API** — `retrieve_similar_chunks` / `search_with_embeddings_fallback`
   in `tools/literature_corpus.py`, wired into
   `agents/literature_evidence.gather_literature_evidence`.
6. **CI-safe path** — default `CORPUS_EMBEDDING_PROVIDER=hash` (deterministic
   stub); no paid API keys required. Keyword fixture search remains the
   fallback when the vector index is empty.

## Acquisition methods

| `acquisition_method` | Meaning | Full-text ingest |
| --- | --- | --- |
| `fixture` | Synthetic CI stubs in-repo | Allowed (`review_status=fixture`) |
| `owner_provided` | User drops files under `data/corpus_private/` | Requires `review_status=approved` + rights fields |
| `licensed` | Explicitly licensed / subscription material | Requires `review_status=approved` + rights fields |

## Copyright / compliance checklist (before real papers)

- [ ] Every source has a Corpus Registry row with complete rights fields.
- [ ] Public accessibility ≠ public domain; do not bulk-download award PDFs.
- [ ] Unclear-rights materials stay metadata/link-only (`full_text_storage_allowed=no`).
- [ ] `external_llm_upload_allowed` stays `no` unless Provider terms are reviewed.
- [ ] Redistribution remains `no` — this system is not a paper redistribution service.
- [ ] Owner confirms first-batch registry + retrieval purpose boundary (PRD §23.3).
- [ ] See also `docs/COMPETITION_COMPLIANCE_CHECKLIST_2027.md`.

## Register a source

1. Copy a row pattern from `knowledge/corpus_registry.csv` or the template.
2. Set `acquisition_method` to `fixture` / `owner_provided` / `licensed`.
3. Fill `license_or_rights_statement`, allowed operations, and review fields.
4. Point `local_path` at a readable text file (fixture snippet or
   `data/corpus_private/<file>.txt`).

## Ingest

```bash
# Local JSON index (default for demos; gitignored under data/corpus_index/)
python -m scripts.corpus.ingest --backend json --clear

# Docker Postgres + pgvector
docker compose up -d postgres
CORPUS_VECTOR_BACKEND=pgvector python -m scripts.corpus.ingest --backend pgvector --clear
```

Embedding providers:

| Provider | Env | Notes |
| --- | --- | --- |
| `hash` (default) | `CORPUS_EMBEDDING_PROVIDER=hash` | Deterministic, offline, CI-safe |
| `sentence_transformers` | optional local models | `pip install sentence-transformers` |
| `openai` | API key required | OpenAI-compatible `/embeddings` |

## Query

```bash
python -m scripts.corpus.query "transaction costs gold bitcoin sensitivity" --limit 5
```

Programmatic API used by Literature:

```python
from tools.literature_corpus import retrieve_similar_chunks, search_with_embeddings_fallback

hits = retrieve_similar_chunks("walk-forward past prices only", limit=5)
sources, backend = search_with_embeddings_fallback(query_text="...", limit=5)
```

Literature agent behavior:

1. Build query from `ProblemSpecification` (+ EDA context).
2. If an embedding index has chunks → rank by cosine similarity.
3. Else → fixture keyword search (`fixture_corpus`).
4. Live remote retrieval remains a separate gated stub (never invents citations).

## Owner private papers

```text
data/corpus_private/          # gitignored except README + .gitkeep
  my_licensed_excerpt.txt
```

1. Confirm you have rights to store/excerpt the text.
2. Add an `owner_provided` or `licensed` registry row with `review_status=approved`.
3. Run ingest locally — do **not** commit the file.

## Tests

```bash
pytest tests/unit/test_corpus_embeddings.py tests/unit/test_literature_evidence.py -q
```

CI uses the hash embedder + in-memory store; Postgres and paid APIs are not required.
