# MCM C Agent — Next Execution Queue

**Checkpoint:** `mcm-c-2026-11-05-phase-b-live-planner`  
**Status:** Paused at Phase B handoff; multi-agent CLI implementation has **not started**.

| Priority | ID | Task | Acceptance / evidence | Owner gate | State |
| --- | --- | --- | --- | --- | --- |
| P0 | MCM-STATE-01 | Preserve runtime checkpoint in GitHub + Google Docs | Links work, SHA recorded, contains no secrets | None for documentation | In progress |
| P0 | MCM-B-ACCEPT-01 | Verify approved AI 3-chart execution | Three rendered images OR explain missing; record actual plan approval and exports | Owner approves chart proposal | Not verified |
| P0 | MCM-B-ACCEPT-02 | Verify exported Markdown/JSON, provenance, labels and units | Concrete files/screenshots; pytest & CI link | User final acceptance | Pending |
| P1 | MCM-RESEARCH-01 | Scope generic Feature Engineering & advanced chart capability | Proposal with formulas, data handling, tests, costs and constraints | Owner approval for research semantics | Not started |
| P1 | MCM-AGENT-01 | Review multi-agent governance PR #3 | Risk tiers, scope, no auto-merge; accepted/rejected changes | Owner | Draft review pending |
| P1 | MCM-AGENT-02 | Design and implement local Python CLI orchestrator V1 | Cursor/Claude CLI capability checks, safe dry-run, bounded loops, isolated branches, tests | Owner approval for installation / login / paid credentials | Blocked until snapshot + connection |
| P2 | MCM-AGENT-03 | First safe builder → reviewer → CI pilot | One Draft PR, objective tests, reviewer findings, no main merge | Owner final decision | Blocked |
| P2 | MCM-PHASE-C-01 | Build Insight Analyst + Reviewer | Evidence-grounded findings, limits, cross-check tests | Scope approved later | Not started |

## The next single executable step

**Resume Phase B at the Human Approval gate for the already-produced AI three-chart plan**. It has been proposed and user-shared; execution and exports are not yet evidenced. Check for a surviving pending plan in Streamlit and approve only if the user accepts it.

If the user wants to prioritize multi-agent CLI setup immediately after the status snapshot, work from Issue #4 and PR #3, **without** assuming Phase B has been fully closed. Keep Phase B acceptance open as a separately tracked task.
