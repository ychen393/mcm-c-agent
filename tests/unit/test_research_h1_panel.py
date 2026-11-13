"""Phase 5 research / H1 panel helpers and session-cache wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from app.research_h1_panel import (
    CRITIQUE_SESSION_KEY,
    PROPOSAL_SESSION_KEY,
    clear_research_h1_caches,
    resolve_displayed_critique,
    resolve_displayed_proposal,
)
from app.session_caches import (
    PHASE5_RESEARCH_SESSION_KEYS,
    clear_derived_session_caches,
    clear_phase5_research_session_caches,
)

REPO = Path(__file__).resolve().parents[2]


def test_clear_research_h1_caches():
    session = {
        PROPOSAL_SESSION_KEY: {"proposal_id": "prop_x"},
        CRITIQUE_SESSION_KEY: {"critique_id": "crit_x"},
        "keep": 1,
    }
    clear_research_h1_caches(session)
    assert PROPOSAL_SESSION_KEY not in session
    assert CRITIQUE_SESSION_KEY not in session
    assert session["keep"] == 1


def test_clear_phase5_keys_via_derived_clear():
    session = {key: {"stale": True} for key in PHASE5_RESEARCH_SESSION_KEYS}
    session["keep"] = True
    clear_phase5_research_session_caches(session)
    for key in PHASE5_RESEARCH_SESSION_KEYS:
        assert key not in session
    clear_derived_session_caches(
        {
            "research_proposal_draft": {"x": 1},
            "debate_critique_draft": {"y": 1},
            "keep": True,
        }
    )


def test_resolve_prefers_recorded_state_over_session_cache():
    session = {PROPOSAL_SESSION_KEY: {"proposal_id": "cached"}}
    recorded = {"research_proposal": {"proposal_id": "recorded", "candidates": []}}
    assert resolve_displayed_proposal(recorded, session)["proposal_id"] == "recorded"
    assert resolve_displayed_proposal({"research_proposal": {}}, session) is None
    assert resolve_displayed_proposal(None, session)["proposal_id"] == "cached"

    session_c = {CRITIQUE_SESSION_KEY: {"critique_id": "cached"}}
    recorded_c = {
        "decision_report": {"critique": {"critique_id": "recorded", "findings": []}}
    }
    assert resolve_displayed_critique(recorded_c, session_c)["critique_id"] == "recorded"
    assert resolve_displayed_critique({"decision_report": {}}, session_c) is None


def test_main_wires_research_h1_panel():
    source = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert "render_research_h1_panel" in source
    tree = ast.parse(source)
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "render_research_h1_panel" in names


def test_h1_panel_uses_approval_cards_and_title_selectbox():
    source = (REPO / "app" / "research_h1_panel.py").read_text(encoding="utf-8")
    assert "render_h1_approval_card" in source
    assert "candidate_display_label" in source
    assert "render_approved_banner" in source
    assert 't("h1.candidate_help")' in source
    en = (REPO / "locales" / "en.json").read_text(encoding="utf-8")
    assert "Shows plan titles" in en
