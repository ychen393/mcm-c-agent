## Phase {{phase}} Independent Evaluator verdict

| Field | Value |
| --- | --- |
| Verdict | **{{verdict}}** |
| HEAD reviewed | `{{head_sha}}` |
| Draft PR | {{pr_url}} |
| P0 | {{p0_count}} |
| P1 | {{p1_count}} |
| P2 | {{p2_count}} |
| Review file | `internal/phase{{phase}}-independent-review.md` |

### Summary

{{summary}}

### Notes

- CI green ≠ approval.
- Evaluator is read-only (no product edits / push / merge / deploy).
- On PASS with P0/P1 clear: Coordinator may auto-start the next phase.
- Owner still required for merge to `main`, deploy, and product H1/H2/H3.
