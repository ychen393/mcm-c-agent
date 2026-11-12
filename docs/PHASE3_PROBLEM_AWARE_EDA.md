# Phase 3 — Problem-aware multi-dataset EDA

**Branch base:** Phase 2 tip `cursor/phase2-problem-analyst-f3eb` @ `76c2ee7` (Draft PR #34)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. No Phase 4 Literature agent.

## Deliverable

Problem-aware exploratory analysis over 1–N CSV/XLSX uploads, conditioned on a validated `ProblemSpecification` when present, with safe relationship suggestions and user-confirmed integration **preview** (never an automatic merge).

## What this phase does

1. **Multi-file intake** — Reuses `build_dataset_bundle` (1–5 files, 20 MiB/file, 50 MiB aggregate, stable `ds_*` IDs). `tools/intake_errors.classify_upload_errors` surfaces clear **per-file** diagnostics when a selection fails.
2. **Independent per-dataset EDA** — Profiles, dictionaries, quality warnings, and qualified columns (`dataset_id.column`) stay disambiguated. Single-file chart planning/approval remains available.
3. **Relationship suggestions** — Deterministic evidence via `profile_relationships` / UI panel; `cannot safely join` when unjustified; no forced concatenation.
4. **User-confirmed integration preview** — Explicit Preview join + **Confirm integration preview (no merge)** records keys, strategy, unmatched/collision warnings into state with `joined=false`.
5. **ProblemSpecification-conditioned plan** — `tools/problem_aware_eda.build_problem_aware_eda_plan` matches uploads to `supplied_datasets`, surfaces constraints such as `c_past_data_only` / `c_only_supplied_data`, and suggests relationship stances from evidence only. Deterministic; **no live LLM required**.
6. **Sanitized persistence** — Compact `eda_report` summaries + `artifact_refs` via `tools/eda_persistence.py`, respecting Phase 1 `sanitize_state_for_persistence` / forbidden keys. Lifecycle may advance to `data_analysis_done` after approved/recorded independent EDA. Reopen remains `reupload_required`.
7. **CI-safe defaults** — Planner and intake are offline; `PROBLEM_ANALYST_USE_LLM` stays off for green CI.
8. **Session cache clears** — `app/session_caches.clear_derived_session_caches` drops ProblemSpecification + Phase 3 plan/preview keys on foundation rebuild, reopen, continue, and **history load** (history does not pop the foundation signature).

## Contracts

| Module | Role |
| --- | --- |
| `schemas/eda_plan.py` | `ProblemAwareEDAPlan` and related items |
| `tools/problem_aware_eda.py` | Deterministic planner |
| `tools/eda_persistence.py` | Compact summaries + artifact/lifecycle persistence |
| `tools/intake_errors.py` | Per-file intake diagnostics |
| `app/eda_plan_panel.py` | Streamlit plan panel |
| `app/relationship_panel.py` | Preview + confirmation (no merge) |

## 2022 MCM C acceptance (EDA slice)

With the Phase 2 fixture/`ProblemSpecification` and uploads `LBMA-GOLD.csv` + `BCHAIN-MKPRU.csv`:

- Files match `supplied_datasets`
- Plan reminds **use-only-past-data** / supplied-data-only
- Date-key relationship may be **suggested for preview** from evidence
- Plan **must not** invent joins or auto-merge gold+bitcoin

Covered by `tests/unit/test_problem_aware_eda.py` (no live LLM).

## Out of scope (Phase 4+)

- Literature & Evidence Agent
- Research strategy / H1
- Modeling, validation, LaTeX
- Silent merge / resample / timezone coerce / unit conversion
- ADR-001 checkpointer (unless already present)
- Merge to `main` / deploy
