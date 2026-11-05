# Multi-Agent Pilot — Builder → Reviewer → CI

**Not yet executed.** A first pilot must be run only after the owner connects the desired external tools.

## Pilot candidate
Low-risk, reversible Streamlit UI regression: ensure `_context_signature` call sites stay synchronized when API Settings parameters change. An existing regression test is in `tests/unit/test_context_signature_calls.py`; the pilot should improve the prevention/verification mechanism without changing project semantics.

## Workflow
1. ChatGPT / owner frames Issue with acceptance criteria and L1 risk classification.
2. Cursor, once authorized, creates a branch off the current Phase B base, implements/tests, and opens a Draft PR.
3. Claude Code, once authorized, reviews the diff independently; do not let it alter the builder branch directly.
4. GitHub Actions validates the PR. Reviewer and CI findings are returned to the builder, no more than two autonomous repair cycles.
5. Provide a concise decision package; do not merge without the required approval.
6. Capture the results and update `docs/PROJECT_STATUS.md`.

## Success criteria
- Developer and reviewer identities/outputs are distinguishable.
- Both have the minimum repository access needed.
- No plaintext secrets in artifacts, logs or PR.
- CI passes and the reviewer references concrete tests and risks.
- A user decision is requested only for the real gate, not for intermediate implementation chatter.
- Pilot completes without a direct push to `main` or hidden spending.

## Failure and rollback
Stop on missing permissions, provider cost issues, agent loops, unreviewed math changes or CI failure. Close the pilot PR without merging and revoke/disconnect integrations if required. No automatic destructive cleanup.
