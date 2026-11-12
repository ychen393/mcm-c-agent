# Phase Evaluator gate (in-repo mirror)

**Ops source of truth (Project store):** `workflows/phase-evaluator-gate.md`  
**Charter (Project store):** `internal/evaluator-charter.md`  
This file is a **durable in-repo mirror** so CI and contributors can assert the gate without the Agent Store.

## When

After each phase Draft PR is open and CI-green (or Builder reports ready for review).

## Desired result

Independent Evaluator PASS (or PASS after bounded P0/P1 fixes) before the next roadmap phase starts. Owner is notified at phase start and when Evaluator blocks; **owner approval still required for merge to `main`, deploy, and H1/H2/H3**.

## Steps

1. Coordinator creates/resumes a dedicated Evaluator worker (**not** the Builder). Prefer one code Builder at a time; Evaluator runs after Builder delivery.
2. Evaluator reviews the phase Draft PR at an exact HEAD for: (a) phase feature completeness vs roadmap/PRD/issue acceptance, (b) code bugs and regressions (incl. security when relevant). **CI green is not approval.**
3. Verdict: `PASS` | `PASS_WITH_NOTES` | `FAIL` with P0/P1/P2. Write `internal/phaseN-independent-review.md` and comment on the PR.
4. On P0/P1: Builder fixes (bounded cycles); Evaluator re-checks only those items.
5. On Evaluator PASS (P0/P1 clear): Coordinator auto-starts the next phase Builder without waiting for a separate owner “accept” message, unless a preference/H-gate says otherwise.
6. Notify owner at: next phase started, Evaluator FAIL after fix budget, budget/H-gate blockers.

## Exceptions

- Owner may waive a P1 in chat.
- Do **not** merge/deploy without explicit owner approval.
- Phase X (Cursor-dev closed loop) stays separate from research-agent product work.

## Checks

Review file exists; PR comment posted; next phase base = accepted prior tip.
