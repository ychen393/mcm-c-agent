# Literature fixture corpus (Phase 4+)

These entries are **CI/offline stubs** for the Literature & Evidence Agent.

- They are **not** contest solution papers and must not be cited as real MCM
  winning papers or as peer-reviewed literature.
- Entries labeled *excellent-paper-style* are **synthetic** structure/method
  references for embedding retrieval demos — never cite them as award winners.
- `source_type` is always `fixture_stub`; `review_status` is `fixture`.
- The agent may only emit evidence cards whose `source_id` exists in an approved
  corpus / registry row.
- Missing coverage for a research question must become an explicit
  `EvidenceGap` (`insufficient` / `unknown`) — never an invented source.
- Registry rows for these stubs live in `knowledge/corpus_registry.csv`
  (`acquisition_method=fixture`).

Live web / publisher retrieval stays behind `LITERATURE_LIVE_RETRIEVAL`
(default off). Embedding ingest/query is documented in
`docs/CORPUS_EMBEDDINGS.md`. Owner-provided texts go in gitignored
`data/corpus_private/` after registry + copyright review.
