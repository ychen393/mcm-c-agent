"""Phase 6 modeling panel helpers and session-cache wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from app.modeling_panel import (
    EXPERIMENT_SESSION_KEY,
    clear_modeling_experiment_cache,
    resolve_displayed_experiment_report,
)
from app.session_caches import (
    PHASE6_MODELING_SESSION_KEYS,
    clear_derived_session_caches,
    clear_phase6_modeling_session_caches,
)

REPO = Path(__file__).resolve().parents[2]


def test_clear_modeling_experiment_cache():
    session = {
        EXPERIMENT_SESSION_KEY: {"report_id": "erep_x"},
        "keep": 1,
    }
    clear_modeling_experiment_cache(session)
    assert EXPERIMENT_SESSION_KEY not in session
    assert session["keep"] == 1


def test_clear_phase6_keys_via_derived_clear():
    session = {key: {"stale": True} for key in PHASE6_MODELING_SESSION_KEYS}
    session["keep"] = True
    clear_phase6_modeling_session_caches(session)
    for key in PHASE6_MODELING_SESSION_KEYS:
        assert key not in session
    clear_derived_session_caches(
        {
            "modeling_experiment_draft": {"x": 1},
            "research_proposal_draft": {"y": 1},
            "keep": True,
        }
    )
    session2 = {
        "modeling_experiment_draft": {"x": 1},
        "research_proposal_draft": {"y": 1},
        "keep": True,
    }
    clear_derived_session_caches(session2)
    assert "modeling_experiment_draft" not in session2
    assert "research_proposal_draft" not in session2
    assert session2["keep"] is True


def test_resolve_prefers_recorded_experiment_over_session_cache():
    session = {EXPERIMENT_SESSION_KEY: {"report_id": "cached"}}
    recorded = {
        "decision_report": {"experiment": {"report_id": "recorded", "runs": []}}
    }
    assert (
        resolve_displayed_experiment_report(recorded, session)["report_id"]
        == "recorded"
    )
    assert resolve_displayed_experiment_report({"decision_report": {}}, session) is None
    assert resolve_displayed_experiment_report(None, session)["report_id"] == "cached"


def test_main_wires_modeling_panel():
    source = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert "render_modeling_experiment_panel" in source
    assert "upload_count=len(uploaded_files)" in source
    tree = ast.parse(source)
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "render_modeling_experiment_panel" in names


def test_modeling_panel_has_fixture_banner_and_viewers():
    source = (REPO / "app" / "modeling_panel.py").read_text(encoding="utf-8")
    assert "render_fixture_vs_uploads_banner" in source
    assert "render_modeling_artifact_viewers" in source
    assert "upload_count" in source
