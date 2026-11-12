# Phase 1 — Project / Dataset / ResearchState Persistence

**Branch base:** Phase 0 tip `cursor/phase0-unified-baseline-ad8e`  
**Issue:** [#26](https://github.com/ychen393/mcm-c-agent/issues/26)  
**Constraint:** Do not merge to `main`. Do not deploy.

## What this phase stores

| ID | Meaning |
| --- | --- |
| `project_id` | User-provided, sanitized via `safe_project_id` |
| `run_id` | `run_<12 hex>` per saved version |
| `dataset_id` | Existing bundle ID (`ds_…`) |
| `artifact_id` | `art_<12 hex>` for saved outputs |

Persisted dataset facts: file name, SHA-256, dataset id, fields (column / qualified names), row/column counts, profile warnings. **Never** raw file bytes, sample cells, or API keys.

Sanitization is **fail-closed**: forbidden keys (`api_key`, provider `*_api_key`, `raw_bytes`, frames, tokens, etc.) anywhere in nested dict/list structures raise before write. `uploaded_files` entries keep an allowlist of provenance fields only.

## Backends

1. **PostgreSQL (preferred)** when `database_url` accepts a connection and schema init succeeds. Tables: `research_projects`, `research_runs`, `dataset_refs`, `artifact_refs`, `approval_decisions` (names avoid the M0 UUID `projects` scaffold).
2. **Local fallback** when Postgres is unreachable or schema init fails:  
   `data/projects/{project_id}/project.json`  
   `data/projects/{project_id}/runs/{run_id}/{run,state,datasets,artifacts,approvals}.json`

Set `PROJECT_STORE_BACKEND=local|postgres|auto` (default `auto`). The UI and logs show which backend is active. Local layout mirrors the DB model so a later Postgres restore can import the same JSON.

## Lifecycle (honest labels)

| Label | Meaning in Phase 1 |
| --- | --- |
| `project_initialized` | Init succeeded; analysis not started |
| `datasets_recorded` | Validated file provenance is in ResearchState |
| `data_analysis_done` | Reserved for approved independent EDA (not joint modeling) |
| `research_task_complete` | **Not reachable** — joint analysis / strategy modeling not implemented |

## Invalidation

Changing problem text, uploaded files, project ID, or model config (provider / model / session revision) changes the foundation input signature. The store:

- marks the previous active run `stale`
- invalidates pending/approved decisions on that run
- opens a new `run_id` / version
- prompts recompute (do not reuse approved stale results)

## Save / reopen / continue / history

- **Save:** automatic on initialize and whenever recorded inputs change; also available via the persistence panel.
- **Reopen / Continue:** restore **provenance and run history only**. Uploaded file bytes and DataFrames are **not** stored. `data_resume=reupload_required` is always set; the UI warns that matching files must be re-uploaded (SHA-256 check via the normal uploader) before EDA. This is **not** a full research resume.
- **History:** version list with lifecycle, dataset count, and signature.
- **Backend change:** `data/projects/.last_store_backend` records the last backend. If `auto` switches (local ↔ postgres), `StoreInfo.backend_mismatch_message` warns that projects are not silently lost.

## Path safety

Local `run_id` values are validated (`run_<12 hex>`) on every read and write. Read-only queries do not `mkdir`. Traversal / absolute paths are rejected without mutating the project tree.

## Out of scope / untested here

- Live PostgreSQL server acceptance (CI uses local + SQLite-backed store exercises; real PG is preferred when reachable but not required for unit CI).
- Full LangGraph research checkpoint / ADR-001 PostgresSaver.
- Problem Analyst → `ProblemSpecification`, problem-aware EDA, joint modeling (Phase 2+).
