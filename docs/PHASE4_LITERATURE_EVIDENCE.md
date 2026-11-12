# Phase 4 — Literature & Evidence Agent

**Branch base:** Phase 3 tip `cursor/phase3-problem-aware-eda-61f5` @ `0ba00b2` (Draft PR #35)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. No Phase 5 / H1.

## Deliverable

Corpus-backed **evidence cards** grounded to a validated `ProblemSpecification` (and optional EDA plan/report), with explicit gaps when evidence is insufficient. CI stays offline/deterministic.

## What this phase does

1. **Typed contracts** — `schemas/evidence.py`: `SourceMetadata`, `EvidenceSnippet`, `MethodNote`, `CitationFields`, `GroundingLink`, `EvidenceCard`, `EvidenceGap`, `LiteratureEvidenceReport`.
2. **Fixture corpus** — `knowledge/fixture_corpus/` synthetic CI stubs (`source_type=fixture_stub`). Not real MCM papers; never cited as peer-reviewed scholarship.
3. **Literature & Evidence Agent** — `agents/literature_evidence.gather_literature_evidence` searches the fixture corpus, builds cards with quotes/method notes/citations, grounds to RQ/objectives/constraints/EDA items, and emits `EvidenceGap` rows when coverage is weak. **No invented sources.**
4. **Live retrieval gate** — `LITERATURE_LIVE_RETRIEVAL` / UI checkbox defaults **off**. When on, Phase 4 records an explicit unavailable stub note and still does not invent remote citations.
5. **Streamlit panel** — `app/literature_panel.py`: Gather evidence → review cards/gaps → **Attach evidence cards into project state** via Phase 1 sanitize (`tools/evidence_persistence.py` → `evidence_report` + `citations`).
6. **Session cache clears** — `literature_evidence_report` cleared with Phase 2/3 derived caches on rebuild / reopen / continue / history load.
7. **CI-safe** — pytest uses fixtures only; no network required.

## Contracts / modules

| Module | Role |
| --- | --- |
| `schemas/evidence.py` | Evidence / literature Pydantic contracts |
| `knowledge/fixture_corpus/` | Offline approved-stub corpus + snippets |
| `tools/literature_corpus.py` | Deterministic load/search |
| `agents/literature_evidence.py` | Agent entry point |
| `tools/evidence_persistence.py` | Sanitize + attach to ResearchState |
| `app/literature_panel.py` | Streamlit review / attach UI |

## AC-04 alignment (slice)

- Every card has `source_id`, title, URL **or** local path, and `source_type`.
- Locator / verification status is explicit; only fixture-local stubs may be `verified_fixture`.
- Uncovered research questions become gaps (`insufficient` / `unknown`), not fabricated citations.

## Out of scope (Phase 5+)

- Research Strategy / Debate / H1 approval as the main deliverable (interfaces may be stubbed later)
- Modeling, validation, LaTeX
- Full copyright corpus release gate / remote publisher APIs
- Merge to `main` / deploy
