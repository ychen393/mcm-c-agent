"""Phase 3 P1: derived EDA session caches clear on rebuild / reopen / history load."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.problem_analyst_panel import PROBLEM_SPEC_SESSION_KEY
from app.session_caches import (
    PHASE3_EDA_SESSION_KEYS,
    clear_derived_session_caches,
    clear_phase3_eda_session_caches,
)

REPO = Path(__file__).resolve().parents[2]

STALE_PLAN = {
    "plan_version": "1.0",
    "problem_id": "stale_phase3_plan",
    "has_problem_specification": True,
    "joined": False,
    "invented_joins": False,
}
STALE_CONFIRMATION = {
    "confirmed": True,
    "merged": False,
    "joined": False,
    "left_dataset_id": "ds_stale_aaaaaaaaaaaa",
    "right_dataset_id": "ds_stale_bbbbbbbbbbbb",
    "left_key": "Date",
    "right_key": "Date",
    "join_type": "inner",
    "status": "preview",
    "reason": None,
    "message": "stale confirmation must not survive history load",
    "warnings": [],
}


def _stale_session() -> dict:
    return {
        PROBLEM_SPEC_SESSION_KEY: {"problem_id": "stale_cached_spec"},
        "problem_aware_eda_plan": dict(STALE_PLAN),
        "integration_preview_confirmation": dict(STALE_CONFIRMATION),
        "integration_preview_result": {"status": "preview", "preview_rows": [{"x": 1}]},
        "integration_preview_selection": {
            "left_dataset_id": "ds_stale_aaaaaaaaaaaa",
            "right_dataset_id": "ds_stale_bbbbbbbbbbbb",
            "left_key": "Date",
            "right_key": "Date",
            "join_type": "inner",
        },
        "other": "keep",
        "foundation_input_signature": "sig-unchanged-on-history-load",
    }


def test_clear_phase3_eda_session_caches_removes_only_phase3_keys():
    session = _stale_session()
    clear_phase3_eda_session_caches(session)
    for key in PHASE3_EDA_SESSION_KEYS:
        assert key not in session
    assert PROBLEM_SPEC_SESSION_KEY in session
    assert session["other"] == "keep"
    assert session["foundation_input_signature"] == "sig-unchanged-on-history-load"


def test_clear_derived_session_caches_clears_phase2_and_phase3():
    session = _stale_session()
    clear_derived_session_caches(session)
    assert PROBLEM_SPEC_SESSION_KEY not in session
    for key in PHASE3_EDA_SESSION_KEYS:
        assert key not in session
    assert session["other"] == "keep"
    # History load must clear caches even when signature is left in place.
    assert session["foundation_input_signature"] == "sig-unchanged-on-history-load"


def test_record_path_cannot_see_stale_confirmation_after_history_clear():
    """Simulate history load (signature unchanged) then the multi-file Record lookups."""
    session = _stale_session()
    clear_derived_session_caches(session)
    plan_payload = session.get("problem_aware_eda_plan")
    confirmation = session.get("integration_preview_confirmation")
    assert plan_payload is None
    assert confirmation is None
    # Compact persist would only embed confirmation when it is a dict.
    assert not isinstance(confirmation, dict)


def test_persistence_panel_calls_shared_clear_on_reopen_continue_history():
    source = (REPO / "app" / "persistence_panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert calls.count("clear_derived_session_caches") >= 3
    assert "clear_problem_specification_cache" not in calls


def test_foundation_panel_uses_shared_derived_clear():
    source = (REPO / "app" / "foundation_panel.py").read_text(encoding="utf-8")
    assert "clear_derived_session_caches" in source
    assert 'st.session_state.pop("problem_aware_eda_plan"' not in source


APP_PATH = REPO / "app" / "main.py"
GOLD = b"Date,USD (PM)\n9/12/2016,1324.60\n9/13/2016,1321.75\n"
BITCOIN = b"Date,Value\n9/11/2016,621.65\n9/12/2016,609.67\n"


@pytest.fixture(autouse=True)
def _forbid_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _called(*_args, **_kwargs):
        raise AssertionError("No model calls in Phase 3 session-cache tests.")

    monkeypatch.setattr("agents.visual_eda_agent.plan_visual_eda", _called)
    monkeypatch.setattr("llm.factory.LLMFactory.create", _called)


def test_reopen_clears_stale_phase3_session_caches_apptest():
    at = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    next(box for box in at.text_input if box.label == "Project name").set_value("Phase3 Cache")
    next(box for box in at.text_input if box.label == "Project ID for saved artifacts").set_value(
        "mcm-p3-cache"
    )
    next(area for area in at.text_area if area.label.startswith("MCM problem statement")).set_value(
        "2022 MCM Problem C Trading Strategies cache clear probe."
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
    assert "last_run" in at.session_state

    # Inject orphan confirmation caches (plan panel may rebuild a fresh plan later).
    at.session_state["integration_preview_confirmation"] = dict(STALE_CONFIRMATION)
    at.session_state["integration_preview_result"] = {
        "status": "preview",
        "message": "stale",
    }
    at.session_state["integration_preview_selection"] = {
        "left_dataset_id": "ds_stale_aaaaaaaaaaaa",
        "right_dataset_id": "ds_stale_bbbbbbbbbbbb",
        "left_key": "Date",
        "right_key": "Date",
        "join_type": "inner",
    }
    at.session_state[PROBLEM_SPEC_SESSION_KEY] = {"problem_id": "stale_cached_spec"}
    assert "integration_preview_confirmation" in at.session_state

    at = next(button for button in at.button if button.label == "Reopen active run").click().run()
    assert not at.exception
    assert "integration_preview_confirmation" not in at.session_state
    assert "integration_preview_result" not in at.session_state
    assert "integration_preview_selection" not in at.session_state
    assert PROBLEM_SPEC_SESSION_KEY not in at.session_state
    # A fresh deterministic plan may be rebuilt after reopen; it must not carry the
    # stale confirmation into Record.
    assert at.session_state.get("integration_preview_confirmation") is None


def test_history_load_clears_stale_phase3_caches_without_signature_pop():
    """History load keeps foundation_input_signature but must still clear Phase 3 keys."""
    session = _stale_session()
    # Mirror persistence_panel history path: load run into last_run, clear caches,
    # do NOT pop foundation_input_signature.
    session["last_run"] = {"run_id": "run_deadbeef0001", "problem_specification": {}}
    session["foundation_initialized"] = True
    clear_derived_session_caches(session)
    for key in PHASE3_EDA_SESSION_KEYS:
        assert key not in session
    assert session["foundation_input_signature"] == "sig-unchanged-on-history-load"
    assert session.get("problem_aware_eda_plan") is None
    assert session.get("integration_preview_confirmation") is None
    # Record path lookups after history load must not see stale confirmation.
    confirmation = session.get("integration_preview_confirmation")
    assert not isinstance(confirmation, dict)
