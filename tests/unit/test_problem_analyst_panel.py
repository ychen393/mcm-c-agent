"""Problem Analyst panel: recorded state outranks orphan session cache (P1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.foundation_panel import UPDATE_MESSAGE
from app.problem_analyst_panel import (
    PROBLEM_SPEC_SESSION_KEY,
    clear_problem_specification_cache,
    resolve_displayed_problem_specification,
)
from tools.problem_spec_2022_c import load_2022_c_fixture

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"

GOLD = b"Date,USD (PM)\n9/12/2016,1324.60\n9/13/2016,1321.75\n"
BITCOIN = b"Date,Value\n9/11/2016,621.65\n9/12/2016,609.67\n"
STALE_SPEC = {
    "version": "1.0",
    "problem_id": "stale_cached_spec",
    "title": "Should Not Remain Visible",
    "research_questions": [
        {
            "id": "rq_stale",
            "statement": "This orphan cache must not outrank a cleared recorded state.",
            "provenance": "unknown",
        }
    ],
    "objectives": [],
    "constraints": [],
    "supplied_datasets": [],
    "assumptions_to_validate": [],
    "required_deliverables": [],
    "unknowns_or_risks": [],
    "subproblems": [
        {
            "id": "sp_stale",
            "title": "Stale subproblem",
            "statement": "Orphan session cache",
            "provenance": "unknown",
            "inputs": ["x"],
            "outputs": ["y"],
            "evidence_needed": ["z"],
            "candidate_methods": ["n/a"],
            "acceptance_criteria": ["cleared on rebuild"],
        }
    ],
    "key_formulas": [],
    "numeric_conditions": [],
    "trading_rules": [],
    "strategy": "deterministic",
}


@pytest.fixture(autouse=True)
def _forbid_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _called(*_args, **_kwargs):
        raise AssertionError("Panel regression must not call a model.")

    monkeypatch.setattr("agents.visual_eda_agent.plan_visual_eda", _called)
    monkeypatch.setattr("llm.factory.LLMFactory.create", _called)


def test_resolve_prefers_recorded_over_orphan_cache():
    session = {PROBLEM_SPEC_SESSION_KEY: STALE_SPEC}
    recorded = {"problem_specification": {"problem_id": "from_recorded", "title": "Recorded"}}
    # recorded non-empty wins
    assert resolve_displayed_problem_specification(recorded, session)["problem_id"] == "from_recorded"


def test_resolve_cleared_recorded_hides_orphan_cache():
    session = {PROBLEM_SPEC_SESSION_KEY: STALE_SPEC}
    recorded = {"problem_specification": {}}
    assert resolve_displayed_problem_specification(recorded, session) is None
    recorded_missing = {"problem_specification": {}}
    assert resolve_displayed_problem_specification(recorded_missing, session) is None


def test_resolve_allows_cache_only_before_initialize():
    session = {PROBLEM_SPEC_SESSION_KEY: STALE_SPEC}
    assert resolve_displayed_problem_specification(None, session)["problem_id"] == "stale_cached_spec"


def test_clear_problem_specification_cache_removes_key():
    session = {PROBLEM_SPEC_SESSION_KEY: STALE_SPEC, "other": 1}
    clear_problem_specification_cache(session)
    assert PROBLEM_SPEC_SESSION_KEY not in session
    assert session["other"] == 1


def _messages(at: AppTest) -> str:
    parts: list[str] = []
    for group in (at.success, at.error, at.info, at.warning, at.caption, at.markdown, at.subheader):
        for widget in group:
            value = getattr(widget, "value", None)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _json_blobs(at: AppTest) -> str:
    blobs: list[str] = []
    for widget in getattr(at, "json", []):
        value = getattr(widget, "value", None)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            blobs.append(json.dumps(value))
        else:
            blobs.append(str(value))
    return "\n".join(blobs)


def test_problem_text_change_clears_stale_session_spec_apptest():
    """P1 regression: editing problem text must not keep showing an orphan cached spec."""
    fixture = load_2022_c_fixture()
    at = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    next(box for box in at.text_input if box.label == "Project name").set_value("2022 MCM C")
    next(box for box in at.text_input if box.label == "Project ID for saved artifacts").set_value(
        "mcm-p1-cache"
    )
    next(area for area in at.text_area if area.label.startswith("MCM problem statement")).set_value(
        fixture
    )
    at = at.run()
    at = at.file_uploader[0].set_value(
        [
            ("LBMA-GOLD.csv", GOLD, "text/csv"),
            ("BCHAIN-MKPRU.csv", BITCOIN, "text/csv"),
        ]
    ).run()
    at = next(button for button in at.button if button.label == "Initialize project").click().run()
    assert not at.exception

    # Simulate a previously validated session cache + recorded copy (as Analyze would).
    at.session_state[PROBLEM_SPEC_SESSION_KEY] = dict(STALE_SPEC)
    at.session_state["last_run"]["problem_specification"] = dict(STALE_SPEC)
    at = at.run()
    assert not at.exception
    assert "stale_cached_spec" in _json_blobs(at) or "stale_cached_spec" in json.dumps(
        at.session_state.get("last_run", {})
    )

    # Changing problem text rebuilds foundation (clears derived products) and must clear cache.
    revised = fixture + "\n\nRevised after review — cache must not linger."
    at = (
        next(area for area in at.text_area if area.label.startswith("MCM problem statement"))
        .set_value(revised)
        .run()
    )
    assert not at.exception
    assert UPDATE_MESSAGE in _messages(at)
    assert PROBLEM_SPEC_SESSION_KEY not in at.session_state
    assert at.session_state["last_run"]["problem_specification"] == {}
    assert "stale_cached_spec" not in _json_blobs(at)
    assert "Should Not Remain Visible" not in _messages(at)
    assert "No ProblemSpecification yet" in _messages(at)
