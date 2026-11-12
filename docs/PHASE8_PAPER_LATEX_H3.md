# Phase 8 — Paper Planner / LaTeX / Reviewer → H3

**Branch base:** Phase 7 tip `cursor/phase7-validation-h2-0286` @ `9f7d5e2` (Draft PR #40)  
**Constraint:** Draft PR only. Do not merge to `main`. Do not deploy. Do not start Phase 9 E2E.

## Deliverable

A CI-safe **Paper Planner / LaTeX / Reviewer** path for the 2022 MCM C trading slice that runs only when human **H2 is approved**, builds a typed outline / section map / bibliography grounded in prior artifacts (no invented citations), emits offline `.tex` / `.bib`, runs a light reviewer checklist, and requires **explicit human H3** Approve / Request-revision. Phase 9 E2E remains blocked until H3 is approved. **H1, H2, and H3 are never auto-approved.**

## What this phase does

1. **Typed contracts** — `schemas/paper.py`: `PaperSection`, `BibEntry`, `PaperOutline`, `LatexBundle`, `PaperReviewReport`, `PaperPackage`, `H3Decision`, `PaperGenerationGateStatus`, `E2EGateStatus`.
2. **Gates** — `paper/gate.py`:
   - Paper generation allowed only when `approval_status.h2 == approved` (delegates to Phase 7 `validation.gate`).
   - Phase 9 E2E allowed only when `approval_status.h3 == approved`.
3. **Deterministic planner** — `paper/planner.py` builds the 2022 C fixture section map from ProblemSpecification / evidence / experiments / validation. Optional LLM outline is a non-executing stub (off by default via `PAPER_USE_LLM` / UI).
4. **LaTeX path** — `paper/latex.py` emits `.tex` / `.bib` offline. PDF compile is optional / best-effort and soft-fails without TeX (not required for CI green).
5. **Light reviewer** — `paper/reviewer.py` checks structure, citation presence, and topic coverage (CI-safe).
6. **Agent** — `agents/paper_planner.run_paper_planner` calls `assert_paper_allowed` first; status advertises `h3_auto_approve=false` and `e2e_requires_h3_approved=true`.
7. **Streamlit H3 panel** — `app/paper_h3_panel.py`: run → outline / bib / review / latex → **Attach** → human **Approve** / **Request revision**. Persists via Phase 1 sanitize (`tools/paper_persistence.py` → `paper_outline`, `latex_source`, `review_report`, `decision_report.paper` / `h3`, `approval_status.h3`).
8. **Session / foundation clears** — `paper_planner_draft` cleared with derived session caches; foundation rebuild clears paper fields with approvals (no stale H3).
9. **CI-safe** — pytest uses fixtures / rules only; no network / live LLM; TeX not required.

## Contracts / modules

| Module | Role |
| --- | --- |
| `schemas/paper.py` | Outline / bib / latex / review / H3 / E2E-gate contracts |
| `paper/gate.py` | Block paper until H2; block E2E until H3 |
| `paper/planner.py` | Deterministic 2022 C fixture outline |
| `paper/latex.py` | Offline `.tex` / `.bib` emission (+ optional PDF soft-fail) |
| `paper/reviewer.py` | Structure / citation / topic checklist |
| `agents/paper_planner.py` | Agent entry + status |
| `tools/paper_persistence.py` | Sanitize + attach + H3 decision persistence |
| `app/paper_h3_panel.py` | Streamlit review / human gate UI |

## H2 / H3 rules (non-negotiable)

- Paper generation runs only when H2 status is `approved`.
- H3 decisions set `decided_by="human"` and `auto_approved=False`.
- Schema + persistence **reject** auto-approved H3 payloads.
- Bibliography entries must be grounded (`invented=False`); unknown cite keys require `citation_gaps` — never invent sources.
- Approving H3 does **not** mark `research_task_complete` and does **not** start Phase 9 E2E.
- Neither H1, H2, nor H3 is ever auto-approved by this phase.

## Out of scope (Phase 9+)

- Full historical 2022 MCM C E2E acceptance
- Phase X Cursor-dev loop
- Merge to `main` / deploy
- Live LLM paper drafting
- Requiring TeX / PDF for CI green
