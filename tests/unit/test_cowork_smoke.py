"""Isolated Issue 8 smoke check. No research behavior."""

SMOKE_MARKER = "issue-8-cowork-smoke-v1"


def test_issue_8_smoke_marker_stays_out_of_research_code():
    assert SMOKE_MARKER == "issue-8-cowork-smoke-v1"
