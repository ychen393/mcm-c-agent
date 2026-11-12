# Phase 6 — Mathematical Modeling & Experiment

**Branch base:** Phase 5 tip `cursor/phase5-research-h1-9050` @ `c9e84ea` (Draft PR #38)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. Do not start Phase 7 Validation / H2.

## Deliverable

A CI-safe **Modeling & Experiment** path for the 2022 MCM C trading slice that runs only when human **H1 is approved** in ResearchState, records params / code refs / metrics / artifacts linked to the approved proposal, and never auto-approves H1 or calls live trading APIs.

## What this phase does

1. **Typed contracts** — `schemas/experiment.py`: `ExperimentParams`, `ExperimentCodeRef`, `MetricResult`, `ModelArtifactRef`, `ProblemConstraintSnapshot`, `ExperimentRun`, `ExperimentReport`.
2. **Constraint extraction** — `modeling/constraints.py` reads initial cash, αgold / αbitcoin, assets, past-data-only, and gold weekday rules from `ProblemSpecification` when present (else 2022 MCM C defaults).
3. **Deterministic runner** — `modeling/runner.py` + synthetic fixture `modeling/fixture_data.py` (not real LBMA / BCHAIN market data). Stub strategies: cash hold, buy/hold gold or bitcoin, trend-follow bitcoin, periodic 50/50 rebalance. Past-data-only decisions; transaction costs applied.
4. **H1 gate** — `modeling/gate.py` + agent/persistence refuse run/persist unless `approval_status.h1 == approved`. H1 is never auto-approved.
5. **Agent** — `agents/modeling_experiment.run_modeling_experiment` builds an `ExperimentReport` linked to the approved proposal / selected candidate.
6. **Streamlit panel** — `app/modeling_panel.py`: configure → run deterministic path → view metrics/artifacts → **Attach** into `experiment_logs` + `model_artifacts` (+ `decision_report.experiment`) via Phase 1 sanitize (`tools/experiment_persistence.py`).
7. **Optional sandboxed Python** — `MODELING_ALLOW_SANDBOXED_PYTHON` / UI checkbox defaults **off**. When on, Phase 6 records an unavailable stub note and does **not** execute arbitrary code.
8. **Session / foundation clears** — `modeling_experiment_draft` cleared with derived session caches; foundation rebuild clears `model_artifacts` (experiment_logs stay as durable logs).
9. **CI-safe** — pytest uses fixtures / rules only; no network / live LLM / live trading APIs.

## Contracts / modules

| Module | Role |
| --- | --- |
| `schemas/experiment.py` | Experiment / metric / artifact contracts |
| `modeling/constraints.py` | ProblemSpecification → trading constraints |
| `modeling/fixture_data.py` | Synthetic CI price fixture |
| `modeling/runner.py` | Deterministic backtest stubs |
| `modeling/gate.py` | Block until human H1 approved |
| `agents/modeling_experiment.py` | Agent entry + status |
| `tools/experiment_persistence.py` | Sanitize + attach to ResearchState |
| `app/modeling_panel.py` | Streamlit configure / run / attach UI |

## H1 / modeling rules (non-negotiable)

- Modeling runs only when H1 status is `approved` in state.
- Schema + persistence reject invented results and live trading API usage.
- Approving H1 (Phase 5) does not auto-start experiments; the user must run Phase 6 explicitly.
- Attaching results sets `workspace_phases.strategy_modeling=experiment_recorded` but does **not** mark `research_task_complete` or start Phase 7 / H2.

## Out of scope (Phase 7+)

- Validation / sensitivity → H2
- LaTeX / H3
- Full historical 2022 MCM C acceptance E2E
- Merge to `main` / deploy
- Arbitrary sandboxed Python strategy execution
