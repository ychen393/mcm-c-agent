"""Phase 4 literature panel helpers and session-cache wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from app.literature_panel import (
    EVIDENCE_REPORT_SESSION_KEY,
    clear_literature_evidence_cache,
    resolve_displayed_evidence_report,
)
from app.session_caches import (
    PHASE4_LITERATURE_SESSION_KEYS,
    clear_derived_session_caches,
    clear_phase4_literature_session_caches,
)

REPO = Path(__file__).resolve().parents[2]


def test_clear_literature_evidence_cache():
    session = {EVIDENCE_REPORT_SESSION_KEY: {"cards": []}, "keep": 1}
    clear_literature_evidence_cache(session)
    assert EVIDENCE_REPORT_SESSION_KEY not in session
    assert session["keep"] == 1


def test_clear_phase4_keys_via_derived_clear():
    session = {key: {"stale": True} for key in PHASE4_LITERATURE_SESSION_KEYS}
    session["keep"] = True
    clear_phase4_literature_session_caches(session)
    for key in PHASE4_LITERATURE_SESSION_KEYS:
        assert key not in session
    clear_derived_session_caches({"literature_evidence_report": {"x": 1}, "keep": True})


def test_resolve_prefers_recorded_state_over_session_cache():
    session = {EVIDENCE_REPORT_SESSION_KEY: {"problem_id": "cached"}}
    recorded = {"evidence_report": {"problem_id": "recorded", "cards": []}}
    assert resolve_displayed_evidence_report(recorded, session)["problem_id"] == "recorded"
    # Empty recorded evidence means do not fall back to orphan cache.
    assert resolve_displayed_evidence_report({"evidence_report": {}}, session) is None
    assert resolve_displayed_evidence_report(None, session)["problem_id"] == "cached"


def test_main_wires_literature_panel():
    source = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert "render_literature_evidence_panel" in source
    tree = ast.parse(source)
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "render_literature_evidence_panel" in names


def test_literature_panel_folds_gaps_into_expander():
    source = (REPO / "app" / "literature_panel.py").read_text(encoding="utf-8")
    assert 't("lit.gaps_expander"' in source
    assert "gaps[:3]" in source
    en = (REPO / "locales" / "en.json").read_text(encoding="utf-8")
    assert "All evidence gaps" in en


def test_main_sidebar_shows_effective_llm_flags():
    source = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    assert 't("chrome.pa_llm_effective"' in source
    assert "problem_analyst_use_llm_ui" in source
    en = (REPO / "locales" / "en.json").read_text(encoding="utf-8")
    assert "Problem Analyst LLM (effective)" in en
