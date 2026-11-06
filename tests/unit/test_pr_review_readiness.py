"""Offline tests: no network calls and no agent invocation."""
import pytest
from tools.pr_review_readiness import evaluate, markdown

SHA = "a" * 40
OTHER = "b" * 40
PR = {
    "number": 17,
    "head": {"sha": SHA, "ref": "feature/demo"},
    "user": {"login": "builder"},
}


def run(status="completed", conclusion="success", sha=SHA, event="pull_request"):
    return [{
        "id": 1,
        "name": "Python tests",
        "event": event,
        "head_sha": sha,
        "head_branch": "feature/demo",
        "status": status,
        "conclusion": conclusion,
        "html_url": "https://github.com/example/runs/1",
    }]


def review(state="APPROVED", sha=SHA, author="reviewer"):
    return [{
        "commit_id": sha,
        "state": state,
        "user": {"login": author},
        "submitted_at": "2026-11-06T00:00:00Z",
        "html_url": "https://github.com/example/review/1",
    }]


def test_no_review_is_not_ready():
    result = evaluate(PR, run(), [])
    assert result["gate"] == "AWAIT_INDEPENDENT_REVIEW"
    assert result["can_merge"] is False
    assert result["can_launch_cursor"] is False


def test_recorded_review_still_requires_owner():
    result = evaluate(PR, run(), review())
    assert result["gate"] == "OWNER_DECISION_REQUIRED"
    assert result["reviewer_isolation"] == "not_verified"


@pytest.mark.parametrize("conclusion", [
    "failure", "cancelled", "timed_out", "startup_failure",
    "action_required", "skipped", "neutral", None,
])
def test_completed_non_success_requires_fix_authorization(conclusion):
    result = evaluate(PR, run(conclusion=conclusion), review())
    assert result["gate"] == "NEEDS_FIX_AUTH"


@pytest.mark.parametrize("status", ["queued", "in_progress", "waiting", "requested"])
def test_unfinished_ci_is_waiting(status):
    assert evaluate(PR, run(status=status, conclusion=None), [])["gate"] == "AWAIT_CI"


def test_push_only_and_stale_ci_do_not_count():
    assert evaluate(PR, run(event="push"), [])["gate"] == "AWAIT_CI"
    assert evaluate(PR, run(sha=OTHER), [])["gate"] == "AWAIT_CI"


def test_stale_or_self_review_does_not_count():
    assert evaluate(PR, run(), review(sha=OTHER))["gate"] == "AWAIT_INDEPENDENT_REVIEW"
    assert evaluate(PR, run(), review(author="builder"))["gate"] == "AWAIT_INDEPENDENT_REVIEW"


def test_changes_requested_requires_fix_authorization():
    assert evaluate(PR, run(), review("CHANGES_REQUESTED"))["gate"] == "NEEDS_FIX_AUTH"


def test_summary_does_not_claim_independent_ai_review():
    summary = markdown(evaluate(PR, run(), review()))
    assert "NOT VERIFIED" in summary
    assert "auto-merge: **OFF**" in summary
    assert "not** an AI code review" in summary


def test_workflow_has_strict_read_only_permissions():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] /
            ".github/workflows/review-readiness.yml").read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "pull-requests: read" in text
    assert "actions: read" in text
    assert "contents: write" not in text
    assert "pull_request_target" not in text
    assert "persist-credentials: false" in text
    assert "@cursor" not in text


@pytest.mark.parametrize("conclusion,expected", [
    ("success", "AWAIT_INDEPENDENT_REVIEW"),
    ("timed_out", "NEEDS_FIX_AUTH"),
    ("cancelled", "NEEDS_FIX_AUTH"),
])
def test_handoff_packet_never_authorizes_cloud_or_merge(conclusion, expected):
    outcome = evaluate(PR, run(conclusion=conclusion), [])
    packet = outcome["handoff"]
    assert outcome["gate"] == expected
    assert packet["head_sha"] == SHA
    assert packet["requires_fresh_owner_authorization"] is True
    assert packet["authorized_cloud_runs"] == 0
    assert packet["automatic_fix_enabled"] is False
    assert outcome["can_merge"] is False


def test_summary_includes_actionable_next_step():
    report = evaluate(PR, run(conclusion="failure"), [])
    summary = markdown(report)
    assert report["next_action"] in summary
    assert "owner must approve" in summary
