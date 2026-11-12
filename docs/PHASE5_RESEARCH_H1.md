# Phase 5 — Research Strategy / Debate → H1

**Branch base:** Phase 4 tip `cursor/phase4-literature-evidence-4e8f` @ `632ac19` (Draft PR #37)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. Do not start Phase 6 Modeling.

## Deliverable

Parallel research / method selection that synthesizes **candidate methods**, critiques them, and requires **explicit human H1** Approve / Request-revision. Modeling remains blocked until H1 is approved. H1 is **never auto-approved**.

## What this phase does

1. **Typed contracts** — `schemas/research.py`: hypotheses, candidate methods, data needs, validation plans, `ResearchProposal`, `DebateCritique`, `H1Decision`, `ModelingGateStatus`.
2. **Research Strategy Agent** — `agents/research_strategy.synthesize_research_proposal` builds candidates from `ProblemSpecification` (+ EDA / Evidence when present). **Deterministic / CI-safe default.** Optional LLM behind `RESEARCH_STRATEGY_USE_LLM` / UI checkbox — **off by default**, non-inventing stub.
3. **Debate / Critic Agent** — `agents/debate_critic.critique_research_proposal` flags contradictions, weak assumptions, evidence / validation gaps **without inventing sources**. Same LLM flag, off by default.
4. **Streamlit H1 panel** — `app/research_h1_panel.py`: synthesize → critique → show proposal + findings → human **Approve** / **Request revision**. Persists via Phase 1 sanitize (`tools/research_persistence.py` → `research_proposal`, `decision_report`, `disagreement_log`, `approval_status.h1`).
5. **Modeling gate** — `modeling/gate.py`: `modeling_allowed` is true **only** when human H1 status is `approved`. Phase 6 is not started by approval.
6. **Session / foundation clears** — Phase 5 draft caches cleared with derived session caches; foundation rebuild clears proposal / decision / disagreement / approvals (no stale H1).
7. **CI-safe** — pytest uses fixtures / rules only; no network / live LLM required.

## Contracts / modules

| Module | Role |
| --- | --- |
| `schemas/research.py` | Proposal / critique / H1 / modeling-gate contracts |
| `agents/research_strategy.py` | Deterministic candidate synthesis |
| `agents/debate_critic.py` | Deterministic critique |
| `tools/research_persistence.py` | Sanitize + attach + H1 decision persistence |
| `modeling/gate.py` | Block Modeling until H1 approved |
| `app/research_h1_panel.py` | Streamlit review / human gate UI |

## H1 rules (non-negotiable)

- H1 decisions set `decided_by="human"` and `auto_approved=False`.
- Schema + persistence **reject** auto-approved payloads.
- Approve requires an explicit selected candidate.
- Request-revision keeps modeling blocked.
- Approving H1 does **not** mark `research_task_complete` and does **not** start Phase 6.

## Out of scope (Phase 6+)

- Mathematical Modeling & Experiment Agent
- H2 / H3
- Merge to `main` / deploy
