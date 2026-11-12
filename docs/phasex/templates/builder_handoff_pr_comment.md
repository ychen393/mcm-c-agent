## Phase {{phase}} Builder handoff

| Field | Value |
| --- | --- |
| Draft PR | {{pr_url}} |
| Branch | `{{branch}}` |
| HEAD | `{{head_sha}}` |
| Base | `{{base_branch}}` @ `{{base_sha}}` |
| Local tests | `pytest -q` → {{pytest_summary}} |
| CI | {{ci_status}} |

### Delivered

{{delivered_bullets}}

### Out of scope

{{out_of_scope_bullets}}

### Next

1. Independent Evaluator review at HEAD `{{head_sha}}` (not the Builder).
2. On PASS (P0/P1 clear): Coordinator may auto-advance the next phase.
3. **No merge to `main` / deploy** without explicit owner approval.
4. Product **H1 / H2 / H3** remain human-only (never auto-approved).
