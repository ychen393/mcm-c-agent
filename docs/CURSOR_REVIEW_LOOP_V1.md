# Builder → Review → Fix → Review (maximum two repairs)

This implementation adds a deterministic two-repair state machine and a read-only GitHub Actions observer. It does NOT add an independently isolated AI Reviewer or automatically launch Cursor Cloud.

## Operational sequence

1. Owner explicitly authorizes one Cursor Builder task after checking included Premium usage and the $0 extra-spend requirement. Auto Top-up being off is not proof of a hard account spend cap.
2. Builder pushes one isolated Draft PR. GitHub Actions runs actual PR-event Pytest.
3. Separate Reviewer reviews the exact head commit. A true GitHub APPROVED/CHANGES_REQUESTED review is evidence; a CI check or read-only token demonstration is NOT independent AI review.
4. For a failing review or CI run, state becomes NEEDS_FIX_AUTH. Owner must separately authorize a fix invocation before any new Cursor Cloud task.
5. Builder submits a new SHA; that consumes fix #1 or #2. CI and review repeat against the new SHA. After the second failed fix review, state becomes EXHAUSTED. No third fix is permitted by the controller.
6. READY_FOR_OWNER means review and CI passed, but never authorizes auto-merge.

## Explicit state transitions

NEEDS_BUILD_AUTH -> AWAIT_BUILD -> AWAIT_CI -> AWAIT_REVIEW -> READY_FOR_OWNER
Review/CI failure -> NEEDS_FIX_AUTH -> AWAIT_FIX -> AWAIT_CI -> AWAIT_REVIEW
At most two FIX submissions. A failing final review/CI -> EXHAUSTED.
BLOCKED can be entered on privacy, security, cost or permissions concerns.

## Usage

Save a JSON array of events, each with a unique id, kind, actor, commit sha and GitHub evidence URL where applicable. Supported kinds: authorize, build, fix, ci_pass, ci_fail, review_pass, review_fail, stop. An authorize event requires the owner's actor name, extra_spend_usd=0 and single_agent=true, but this is a recorded attestation, not billing enforcement.

Run: python -m tools.cowork_review_loop replay --events ledger.json --owner ychen393 --builder 'cursor[bot]'

For a live advisory snapshot: GH_TOKEN from your secure environment, then python -m tools.cowork_review_loop github --repo ychen393/mcm-c-agent --pr 14. Never place tokens in the repository or chat.

A PR event runs the GitHub observer, and a pull_request_review event can refresh the evidence summary. The observer reads commits, reviews and PR-event test runs but never changes source code, comments, permissions, or launches agents. Its observed fix count is advisory and may undercount CI-only iterations; persist the replay ledger to enforce the two-fix limit inside this tool.

## Status/limitations

The loop engine can enforce two fixes when invoked through its explicit event ledger. The GitHub observer cannot hard-block external Git pushes or Cursor Cloud invocations. Reviewer tool-enforced read-only isolation is still BLOCKED in the observed Cloud session. No automated Fix dispatch is enabled because user requires explicit authorization per Cloud run and $0 additional billed usage. No production MCM statistical semantics have been altered.
