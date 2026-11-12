# Phase 2 — Problem Analyst → ProblemSpecification

**Branch base:** Phase 1 tip `cursor/phase1-project-persistence-f8a4` @ `a24ba1d`  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. No secrets/billing changes.

## Deliverable

Given an MCM C problem statement (starting with **2022 MCM Problem C — Trading Strategies**), the system produces a validated Pydantic `ProblemSpecification` — not raw text display.

Contract: `schemas/problem_specification.py`

| Section | Purpose |
| --- | --- |
| Problem ID / Title | Stable identity for downstream agents |
| Research Questions | Official contest questions |
| Objectives | Return / decision objectives |
| Constraints | Capital, calendars, costs, information, data-use |
| Supplied Datasets | File names + column descriptions |
| Assumptions to Validate | Inferred or unknown assumptions |
| Required Deliverables | Summary, TOC, memo, references, page limit |
| Unknowns / Risks | Explicit gaps (no silent invention) |
| Subproblems | Per-question inputs / outputs / evidence / methods / acceptance |
| key_formulas / numeric_conditions / trading_rules | Source-marked critical facts |

Provenance on statements: **`official`** | **`inferred`** | **`unknown`**. Official items require a non-empty `source_excerpt`.

## Execution paths

1. **Deterministic (default, CI):** `tools/problem_spec_2022_c.py` matches 2022 C signatures in the pasted text, verifies required excerpts, and emits a typed specification. Fixture: `data/problem_fixtures/2022_mcm_c_trading_strategies.txt` (© COMAP attribution retained).
2. **Optional LLM:** `PROBLEM_ANALYST_USE_LLM=true` or UI checkbox / `analyze_problem(..., use_llm=True)`. Output must validate; **one** structured repair attempt; on persistent failure for 2022 C, recover via the deterministic extractor rather than inventing facts.

Entry point: `agents/problem_analyst.py` → `analyze_problem()`.

## 2022 C acceptance facts

The specification must accurately identify:

- Initial capital **$1000** / state **[1000, 0, 0]**
- Assets: **gold** and **bitcoin** (plus cash)
- Trading-day limits: bitcoin every day; gold only on market-open days
- Transaction costs: **αgold = 1%**, **αbitcoin = 2%**; no hold cost
- **Use-only-past-data** rule for daily decisions
- Supplied files: `LBMA-GOLD.csv`, `BCHAIN-MKPRU.csv`

Covered by `tests/unit/test_problem_analyst.py` using the fixture text (no live LLM required).

## UI

Research Lab → **Problem Analyst** panel: Analyze problem → show validated JSON. Does **not** claim joint analysis or strategy modeling is complete.

## Out of scope (Phase 3+)

- Problem-aware multi-dataset EDA / joins → see `docs/PHASE3_PROBLEM_AWARE_EDA.md`
- Literature & Evidence Agent
- Research strategy / H1
- Modeling, validation, LaTeX
