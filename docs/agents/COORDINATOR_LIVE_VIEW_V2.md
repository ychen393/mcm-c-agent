# Coordinator V2 — Automatically refreshed GitHub task snapshot

This is an **event-driven GitHub snapshot** (not a live Cursor Project dashboard). It builds directly on the MCM development [Agent Registry](AGENT_REGISTRY.md) and [Task Registry](task-registry.json).

## How to use

After the branch containing this workflow has an eligible PR, GitHub Actions runs **Coordinator snapshot (read-only)** on new PRs, PR updates, and review submissions. A manual `workflow_dispatch` is also available after the workflow is installed in an eligible GitHub default-branch context.

1. Open the Actions tab and select **Coordinator snapshot (read-only)**.
2. Open the latest run on the desired branch/PR and read the **Job Summary**.
3. Under **Artifacts**, open `coordinator-view`. It contains `index.html`, `tasks.json`, and `SUMMARY.md`.
4. Each task includes its declared role, historical Cursor session link (only if recorded), exact current PR HEAD, matching PR-native Python CI, latest GitHub review for that commit, and next owner decision.

No server is deployed and no Cursor Project pages are modified. A GitHub artifact is an exported HTML file, not a hosted website or constantly updating page. The snapshot is current only as of its `collected_at_utc` timestamp.

## Limitations and correctness

- The static Task Registry defines **which** tasks exist; GitHub supplies **their observed PR/CI/review state**. New tasks and Cursor session IDs still need explicit registry updates. Cursor session metadata is not available to this GitHub job.
- If PR HEAD moves, review evidence from older HEADs is not accepted. Self-approval is not accepted.
- Successful CI does not prove mathematical correctness or a permission-isolated AI Reviewer.
- Github review existence alone is not tool isolation; `isolated_ai_reviewer_verified` remains false.
- Missing CI is `AWAIT_CI`, inaccessible API calls become `FETCH_BLOCKED`. No hallucinated success.
- The project-level Coordinator in Cursor is a separate product UI; these artifacts only provide a unified *external* task list and deep links back to observed sessions.
- Workflow has only GitHub **read** permissions. It creates no issues, PR comments, Cloud agents, Cursor Automations or billable AI calls. GitHub Actions minutes/storage may count against plan quotas; **USD $0 extra billed budget** remains the user policy.

## Further integration gate

To display this view *inside* the Cursor Project with continuous session sync, a supported Cursor Project API or explicit browser/UI integration must first be verified. Do not call a conversation an agent or claim Project-native orchestration without direct evidence.

## Exact boundaries

No auto-fix, child dispatch, recurring Cursor Cloud, paid API, merge, deployment, secret changes, or research checkpoint changes.
