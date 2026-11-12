# Phase 7 — Validation / Sensitivity → H2

**Branch base:** Phase 6 tip `cursor/phase6-modeling-experiment-a16b` @ `7cbf23e` (Draft PR #39)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. Do not start Phase 8 Paper / LaTeX / H3.

## Deliverable

A CI-safe **Validation / Sensitivity** path for the 2022 MCM C trading slice that runs only when human **H1 is approved** and Phase 6 **experiment results are available**, records metrics / scenarios / robustness notes linked to those experiments, and requires **explicit human H2** Approve / Request-revision. Paper / LaTeX remains blocked until H2 is approved. **H1 and H2 are never auto-approved.**

## What this phase does

1. **Typed contracts** — `schemas/validation.py`: `MetricSnapshot`, `MetricDelta`, `PerturbationSpec`, `SensitivityScenario`, `RobustnessNote`, `ValidationReport`, `H2Decision`, `ValidationGateStatus`, `PaperGateStatus`.
2. **Gates** — `validation/gate.py`:
   - Validation allowed only when `approval_status.h1 == approved` **and** usable Phase 6 experiment results exist (`decision_report.experiment` or completed `experiment_logs`).
   - Paper allowed only when `approval_status.h2 == approved`.
3. **Deterministic runner** — `validation/runner.py` reuses the Phase 6 synthetic fixture + backtest stubs; perturbs αgold / αbitcoin, lookback_days, and rebalance_every_n_days. Optional LLM critique is a non-executing stub (off by default via `VALIDATION_USE_LLM` / UI checkbox).
4. **Agent** — `agents/validation_sensitivity.run_validation_sensitivity` builds a `ValidationReport` linked to the baseline experiment run.
5. **Streamlit H2 panel** — `app/validation_h2_panel.py`: run sensitivity → show baseline / scenarios / robustness → **Attach** → human **Approve** / **Request revision**. Persists via Phase 1 sanitize (`tools/validation_persistence.py` → `validation_report`, `decision_report.validation` / `h2`, `approval_status.h2`).
6. **Session / foundation clears** — `validation_sensitivity_draft` cleared with derived session caches; foundation rebuild clears `validation_report` with approvals (no stale H2).
7. **CI-safe** — pytest uses fixtures / rules only; no network / live LLM / live trading APIs.

## Contracts / modules

| Module | Role |
| --- | --- |
| `schemas/validation.py` | Validation / sensitivity / H2 / paper-gate contracts |
| `validation/gate.py` | Block validation until H1+experiments; block paper until H2 |
| `validation/runner.py` | Deterministic sensitivity over Phase 6 fixture outputs |
| `agents/validation_sensitivity.py` | Agent entry + status |
| `tools/validation_persistence.py` | Sanitize + attach + H2 decision persistence |
| `app/validation_h2_panel.py` | Streamlit review / human gate UI |

## H1 / H2 rules (non-negotiable)

- Validation runs only when H1 status is `approved` **and** experiment results are available.
- H2 decisions set `decided_by="human"` and `auto_approved=False`.
- Schema + persistence **reject** auto-approved H2 payloads.
- Approving H2 does **not** mark `research_task_complete` and does **not** start Phase 8 Paper / LaTeX.
- Neither H1 nor H2 is ever auto-approved by this phase.

## Out of scope (Phase 8+)

- Paper Planner / LaTeX / Reviewer → H3
- Full historical 2022 MCM C acceptance E2E
- Merge to `main` / deploy
- Live LLM validation critique
