"""Phase 7 validation / H2 panel helpers and session-cache wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from app.session_caches import (
    PHASE7_VALIDATION_SESSION_KEYS,
    clear_derived_session_caches,
    clear_phase7_validation_session_caches,
)
from app.validation_h2_panel import (
    VALIDATION_SESSION_KEY,
    clear_validation_h2_caches,
    resolve_displayed_validation_report,
)

REPO = Path(__file__).resolve().parents[2]


def test_clear_validation_h2_caches():
    session = {
        VALIDATION_SESSION_KEY: {"report_id": "vrep_x"},
        "keep": 1,
    }
    clear_validation_h2_caches(session)
    assert VALIDATION_SESSION_KEY not in session
    assert session["keep"] == 1


def test_clear_phase7_keys_via_derived_clear():
    session = {key: {"stale": True} for key in PHASE7_VALIDATION_SESSION_KEYS}
    session["keep"] = True
    clear_phase7_validation_session_caches(session)
    for key in PHASE7_VALIDATION_SESSION_KEYS:
        assert key not in session
    session2 = {
        "validation_sensitivity_draft": {"x": 1},
        "modeling_experiment_draft": {"y": 1},
        "keep": True,
    }
    clear_derived_session_caches(session2)
    assert "validation_sensitivity_draft" not in session2
    assert "modeling_experiment_draft" not in session2
    assert session2["keep"] is True


def test_resolve_prefers_recorded_validation_over_session_cache():
    session = {VALIDATION_SESSION_KEY: {"report_id": "cached"}}
    recorded = {"validation_report": {"report_id": "recorded", "scenarios": []}}
    assert (
        resolve_displayed_validation_report(recorded, session)["report_id"]
        == "recorded"
    )
    # Empty recorded run still surfaces the unattached draft so Attach works.
    assert resolve_displayed_validation_report({}, session)["report_id"] == "cached"
    assert resolve_displayed_validation_report(None, session)["report_id"] == "cached"
    assert resolve_displayed_validation_report({}, {}) is None


def test_resolve_falls_back_to_decision_report_validation():
    recorded = {
        "decision_report": {"validation": {"report_id": "nested_vrep"}},
    }
    assert (
        resolve_displayed_validation_report(recorded, {})["report_id"]
        == "nested_vrep"
    )


def test_main_wires_validation_h2_panel():
    source = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert "render_validation_h2_panel" in source
    tree = ast.parse(source)
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "render_validation_h2_panel" in names
