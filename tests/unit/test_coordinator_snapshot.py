"""Offline tests for coordinator snapshot with mocked GitHub evidence."""
from copy import deepcopy
from html.parser import HTMLParser
from tools.coordinator_snapshot import collect, refresh_entry, render_html, render_markdown

SHA = "f" * 40
ENTRY = {
    "task_id": "pilot", "pr": 20, "role": "coordinator",
    "session": "https://cursor.com/agents/bc-real",
    "next_gate": "Owner review",
}
PR = {
    "head": {"sha": SHA, "ref": "feature/demo"},
    "state": "open", "merged": False, "draft": True,
    "html_url": "https://github.com/sample/project/pull/20",
    "user": {"login": "builder"},
}


def api(conclusion="success", review=None, state="completed", sha=SHA):
    def fetch(repo, route):
        if route == "pulls/20":
            return deepcopy(PR)
        if route.startswith("actions/runs?"):
            return {"workflow_runs": [{
                "id": 3, "name": "Python tests", "event": "pull_request",
                "head_sha": sha, "head_branch": "feature/demo",
                "status": state, "conclusion": conclusion,
                "html_url": "https://github.com/sample/project/actions/runs/3",
            }]}
        if route == "pulls/20/reviews?per_page=100":
            return review or []
        raise AssertionError(route)
    return fetch


def test_green_ci_without_review_never_authorizes_merge():
    result = refresh_entry(ENTRY, "sample/project", api())
    assert result["live"]["state"] == "AWAIT_REVIEW"
    assert result["live"]["can_auto_merge"] is False
    assert result["live"]["can_auto_dispatch"] is False


def test_stale_ci_does_not_count():
    result = refresh_entry(ENTRY, "sample/project", api(sha="a" * 40))
    assert result["live"]["state"] == "AWAIT_CI"


def test_cancelled_ci_needs_owner_fix_auth():
    for status in ("cancelled", "timed_out", "failure", "startup_failure"):
        result = refresh_entry(ENTRY, "sample/project", api(conclusion=status))
        assert result["live"]["state"] == "NEEDS_FIX_AUTH"


def test_self_review_not_counted_and_distinct_review_does_not_merge():
    review = [{"commit_id": SHA, "state": "APPROVED",
               "user": {"login": "builder"}}]
    assert refresh_entry(ENTRY, "sample/project", api(review=review))["live"]["state"] == "AWAIT_REVIEW"
    review[0]["user"]["login"] = "independent"
    result = refresh_entry(ENTRY, "sample/project", api(review=review))
    assert result["live"]["state"] == "OWNER_DECISION_REQUIRED"
    assert result["live"]["isolated_ai_reviewer_verified"] is False


def test_escaping_and_static_cursor_link():
    entry = dict(ENTRY, task_id='<script>alert(1)</script>',
                 next_gate='<img src=x onerror=alert(1)>')
    data = collect({"project": "Demo", "entries": [entry]}, "sample/project", api())
    html = render_html(data)
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "bc-real" in html
    assert "auto" in html
    assert "GitHub snapshot" in render_markdown(data)


def test_missing_session_and_api_failure_are_not_invented():
    def broken(_repo, _route):
        raise ValueError("inaccessible")
    entry = dict(ENTRY, session=None)
    result = refresh_entry(entry, "sample/project", broken)
    assert result["live"]["state"] == "FETCH_BLOCKED"
    data = collect({"entries": [entry]}, "sample/project", broken)
    assert "Not recorded" in render_html(data)


def test_no_pr_remains_registry_only():
    assert refresh_entry({"task_id": "docs", "pr": None}, "sample/project", api())["live"]["state"] == "NO_PR"


def test_workflow_has_read_permissions_only():
    from pathlib import Path
    yml = (Path(__file__).resolve().parents[2] /
           ".github/workflows/coordinator-snapshot.yml").read_text(encoding="utf-8")
    assert "contents: read" in yml
    assert "pull-requests: read" in yml
    assert "actions: read" in yml
    assert "contents: write" not in yml
    assert "persist-credentials: false" in yml
    assert "pull_request_target:" not in yml
