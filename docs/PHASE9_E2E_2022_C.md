# Phase 9 — 2022 MCM C historical E2E acceptance

**Branch base:** Phase 8 tip `cursor/phase8-paper-latex-h3-a214` @ `dee2a5a` (Draft PR #41)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. Do not start Phase X.

## Deliverable

A CI-safe **offline end-to-end acceptance harness** for **2022 MCM Problem C — Trading Strategies** that walks the product chain with fixtures:

`ProblemSpec → EDA → Evidence → Research/H1 → Modeling → Validation/H2 → Paper/H3 → acceptance`

and asserts golden facts (cash **$1000**, gold+bitcoin, αgold/αbitcoin costs, past-data-only, official CSVs, human gates, non-invented citations).

## Human gates: harness vs product UI

| Gate | Product UI (human-only) | Phase 9 harness (test double) |
| --- | --- | --- |
| **H1** | `app/research_h1_panel.py` — explicit Approve / Request-revision | `e2e.human_gates.apply_harness_h1_approval` |
| **H2** | `app/validation_h2_panel.py` — explicit Approve / Request-revision | `e2e.human_gates.apply_harness_h2_approval` |
| **H3** | `app/paper_h3_panel.py` — explicit Approve / Request-revision | `e2e.human_gates.apply_harness_h3_approval` |

**Non-negotiable**

- Harness doubles call the same `build_h*_decision` / `persist_h*_decision_into_state` paths as the UI.
- Decisions always use `decided_by="human"` and `auto_approved=False`.
- Provenance is stamped under `decision_report.e2e_harness.gates` with `harness_simulated_human=True` and `representation="harness_test_double"`.
- **H1, H2, and H3 are never auto-approved** in product code or in this harness.
- The harness does **not** set `lifecycle=research_task_complete` and does **not** merge/deploy.

## What this phase does

1. **Typed contracts** — `schemas/e2e.py`: `AcceptanceFactCheck`, `HarnessGateRecord`, `E2EStepResult`, `E2EAcceptanceReport`.
2. **Acceptance facts** — `e2e/acceptance_facts.py` catalogues cash / assets / costs / CSVs / gates.
3. **Harness** — `e2e/harness.py` `run_2022_c_historical_e2e` walks the offline chain and calls `assert_e2e_allowed` only after harness H3.
4. **Golden checks** — `e2e/assertions.py` verifies critical artifacts exist and citations are not invented.
5. **Optional CLI** — `python -m e2e.cli` (pytest remains the CI path).
6. **CI-safe** — no network, live LLM, live retrieval, or live trading required for green.

## Modules

| Module | Role |
| --- | --- |
| `schemas/e2e.py` | E2E report / step / gate-double contracts |
| `e2e/acceptance_facts.py` | Golden 2022 C fact catalogue |
| `e2e/human_gates.py` | Harness simulated-human gate doubles + product vs harness docs |
| `e2e/harness.py` | Offline chain walker |
| `e2e/assertions.py` | Golden / regression fact checks |
| `e2e/cli.py` | Optional CLI entry |
| `tests/e2e/test_2022_c_historical_acceptance.py` | Pytest E2E suite |

## Acceptance facts asserted

- Initial cash **$1000**
- Assets **gold** + **bitcoin**
- Transaction costs **αgold = 1%**, **αbitcoin = 2%**
- **Past-data-only** constraint
- Official CSVs **LBMA-GOLD.csv** + **BCHAIN-MKPRU.csv**
- Artifacts: ProblemSpec, evidence, proposal, experiment, validation, paper outline, LaTeX, review
- Citations / bibliography **not invented**
- H1 / H2 / H3 approved with `auto_approved=False`, `decided_by=human`
- E2E allowed only after H3

## How to run

```bash
pytest -q tests/e2e tests/unit/test_e2e_contract.py
# or full suite
pytest -q
# optional CLI
python -m e2e.cli
```

## Out of scope

- Phase X Cursor development-agent closed loop
- Merge to `main` / deploy
- Live LLM / live retrieval required for CI green
- Production auto-approve of H1 / H2 / H3
