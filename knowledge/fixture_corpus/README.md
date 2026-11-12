# Literature fixture corpus (Phase 4)

These entries are **CI/offline stubs** for the Literature & Evidence Agent.

- They are **not** contest solution papers and must not be cited as real MCM
  winning papers or as peer-reviewed literature.
- `source_type` is always `fixture_stub`; `review_status` is `fixture`.
- The agent may only emit evidence cards whose `source_id` exists in this bundle.
- Missing coverage for a research question must become an explicit
  `EvidenceGap` (`insufficient` / `unknown`) — never an invented source.

Live web / publisher retrieval stays behind `LITERATURE_LIVE_RETRIEVAL`
(default off) and is out of scope for green CI.
