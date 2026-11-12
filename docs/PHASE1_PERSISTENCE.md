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
- **Reopen:** load a saved project’s active run into the session.
- **Continue:** resume the active (or selected) run; stale historical runs surface an explicit warning.
- **History:** version list with lifecycle, dataset count, and signature.

## Out of scope (Phase 2+)

Problem Analyst → `ProblemSpecification`, problem-aware EDA, literature agent, and LangGraph Postgres checkpointer spike remain later phases.
