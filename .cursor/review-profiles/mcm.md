# MCM C Agent review profile

This is an extension to `universal-reviewer.md` for the `ychen393/mcm-c-agent` repository. It adds domain-specific review checks; it does NOT authorize research changes or certify mathematical correctness.

## Source of truth and hard gates
- Read `AGENTS.md`, `docs/AUTONOMY_POLICY.md`, `docs/PRD.md` and the corresponding issue/PR. Compare `docs/RUN_STATE.md`, `docs/NEXT_ACTIONS.md`, `docs/state/mcm_checkpoint.json` and `docs/mcm-runtime-checkpoint` when the change touches research/runtime state, if present on the selected branch.
- Preserve Phase B research checkpoint and pending chart execution/export acceptance. Do not silently advance Phase C or mark advanced EDA complete.
- L2+ modeling scope, score definitions, transformations, contest compliance and publication decisions require owner review.
- No datasets or private prompts copied to outside providers. Explicitly note whether synthetic fixtures were used.

## Math and statistics
- Validate dimensions/units, identifiability, edge cases, missingness and outliers; distinguish correlation from causation.
- Inspect transformations for provenance, leakage, train/test leakage, choice of denominators, uncertainty and numerical stability.
- Require deterministically recomputable numbers from Python/approved numerical code; LLM proposed chart specs must not be presented as executed results.
- Cross-check charts against source columns, aggregation formulas, filters, scales and reported findings.
- Verify claims in generated report/LaTeX correspond to real calculation outputs and sources. No fabricated references or results.

## Agent and code workflow
- Check agent state transitions, retries, tool allowlists, cost/timeout stop gates, schema validation and error recovery.
- Specifically check `timed_out`, `cancelled`, `startup_failure`, stale SHA/CI events, replay idempotency, and two-fix exhaustion when relevant.
- A `pull_request` green check is not a specialized reviewer; a `readonly` frontmatter key is not security enforcement.
- Never label Cursor Bugbot, ChatGPT coordinator, or GitHub Actions Observer as an independently isolated reviewer unless a separate principal and scope are verified.

## Deliverable
Report domain-specific findings separately from generic code findings and explicitly label any mathematical claims that could not be verified without data, accepted assumptions or external proof.
