"""Phase 8 paper / H3 panel helpers and session-cache wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from app.paper_h3_panel import (
    PAPER_SESSION_KEY,
    clear_paper_h3_caches,
    resolve_displayed_paper_package,
)
from app.session_caches import (
    PHASE8_PAPER_SESSION_KEYS,
    clear_derived_session_caches,
    clear_phase8_paper_session_caches,
)

REPO = Path(__file__).resolve().parents[2]


def test_clear_paper_h3_caches():
    session = {
        PAPER_SESSION_KEY: {"package_id": "ppkg_x"},
        "keep": 1,
    }
    clear_paper_h3_caches(session)
    assert PAPER_SESSION_KEY not in session
    assert session["keep"] == 1


def test_clear_phase8_keys_via_derived_clear():
    session = {key: {"stale": True} for key in PHASE8_PAPER_SESSION_KEYS}
    session["keep"] = True
    clear_phase8_paper_session_caches(session)
    for key in PHASE8_PAPER_SESSION_KEYS:
        assert key not in session
    session2 = {
        "paper_planner_draft": {"x": 1},
        "validation_sensitivity_draft": {"y": 1},
        "keep": True,
    }
    clear_derived_session_caches(session2)
    assert "paper_planner_draft" not in session2
    assert "validation_sensitivity_draft" not in session2
    assert session2["keep"] is True


def test_resolve_prefers_recorded_paper_over_session_cache():
    session = {PAPER_SESSION_KEY: {"package_id": "cached"}}
    recorded = {
        "decision_report": {
            "paper": {"package_id": "recorded", "outline": {"outline_id": "pout_r"}}
        }
    }
    assert (
        resolve_displayed_paper_package(recorded, session)["package_id"] == "recorded"
    )
    # Empty recorded run still surfaces the unattached draft so Attach works.
    assert resolve_displayed_paper_package({}, session)["package_id"] == "cached"
    assert resolve_displayed_paper_package(None, session)["package_id"] == "cached"
    assert resolve_displayed_paper_package({}, {}) is None


def test_resolve_falls_back_to_paper_outline_fields():
    recorded = {
        "paper_outline": {"outline_id": "pout_nested", "package_id": "ppkg_nested"},
        "latex_source": "\\begin{document}\\end{document}",
        "review_report": {"review_id": "prev_x", "bib_source": "@misc{a,}"},
    }
    resolved = resolve_displayed_paper_package(recorded, {})
    assert resolved["outline"]["outline_id"] == "pout_nested"
    assert resolved["latex"]["tex_source"]
    assert resolved["review"]["review_id"] == "prev_x"


def test_main_wires_paper_h3_panel():
    source = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert "render_paper_h3_panel" in source
    tree = ast.parse(source)
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "render_paper_h3_panel" in names
