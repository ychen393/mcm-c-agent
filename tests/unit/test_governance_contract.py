"""Guard that multi-agent governance remains discoverable and explicit.

These tests verify the documentation contract only; they cannot prove that external
coding agents, repository protections, or independent reviews are actually connected.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_agent_policy_exists_and_retains_approval_boundaries():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    autonomy = (ROOT / "docs/AUTONOMY_POLICY.md").read_text(encoding="utf-8")

    assert "Cursor" in agents
    assert "Claude Code" in agents
    assert "pytest -q" in agents
    assert "Never merge" in agents
    for risk in ("L0", "L1", "L2", "L3", "L4"):
        assert risk in autonomy
    assert "No auto-merge enabled" in autonomy
    assert "No self-approval" in autonomy
    assert "API" in autonomy


def test_issue_templates_and_pr_template_present():
    for path in (
        ".github/ISSUE_TEMPLATE/feature.yml",
        ".github/ISSUE_TEMPLATE/bug.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ):
        assert (ROOT / path).is_file(), path
    pr = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert "Independent reviewer" in pr
    assert "Owner approval gate" in pr
    assert "do not auto-merge" in pr


def test_project_status_does_not_claim_connected_external_agents():
    status = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "Not connected" in status
    assert "Draft PR" in status
    assert "not a live dashboard" in status


def test_cursor_subagent_prompts_keep_builder_and_reviewer_separate():
    builder = (ROOT / ".cursor/agents/builder.md").read_text(encoding="utf-8")
    reviewer = (ROOT / ".cursor/agents/reviewer.md").read_text(encoding="utf-8")

    assert "name: builder" in builder
    assert "readonly: false" in builder
    assert "pytest -q" in builder
    assert "Do not mark the change as independently reviewed." in builder
    assert "Pushing to `main`" in builder

    assert "name: reviewer" in reviewer
    assert "readonly: true" in reviewer
    assert "edit the Builder branch" in reviewer
    assert "A second model is not a substitute for numeric or integration tests." in reviewer
    assert "Do not write that the change is approved to merge." in reviewer
    assert "Claude Code" in reviewer

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert ".cursor/agents/builder.md" in agents
    assert ".cursor/agents/reviewer.md" in agents
    status = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "local instruction files" in status
    assert "invalid `subagent_type`" in status


_CI_BASES = ("main", "feature/**", "cursor/**", "test/**")


def _workflow_event_block(workflow: str, event: str) -> str:
    """Return the mapping nested under one top-level `on:` event."""
    lines = workflow.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(f"  {event}:"):
            start = index
            break
    assert start is not None, event
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("   ") and line.strip():
            break
        block.append(line)
    return "\n".join(block)


def test_pull_request_ci_covers_isolated_pr_bases_and_stays_read_only():
    """Lock the PR-native trigger list and the permissions this workflow may have.

    A push run on some other branch is not a pull-request check. The branches
    filter is the pull request base, so cursor/** and test/** have to be present
    or Draft PRs onto those bases never attach this workflow.
    """
    ci = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "pull_request:" in ci
    assert "push:" in ci

    pull_request = _workflow_event_block(ci, "pull_request")
    push = _workflow_event_block(ci, "push")
    for base in _CI_BASES:
        assert f'"{base}"' in pull_request or f"- {base}" in pull_request
        assert f'"{base}"' in push or f"- {base}" in push
    for activity in ("opened", "synchronize", "reopened", "ready_for_review"):
        assert activity in pull_request

    assert "permissions:" in ci
    assert "contents: read" in ci
    assert "contents: write" not in ci
    assert "pull_request_target:" not in ci
    assert "workflow_run:" not in ci
    assert "secrets." not in ci
    assert 'python-version: "3.11"' in ci
    assert "timeout-minutes: 20" in ci
    assert "persist-credentials: false" in ci
    assert "pytest -q" in ci
    assert "cancel-in-progress: true" in ci
    assert "github.event_name" in ci
