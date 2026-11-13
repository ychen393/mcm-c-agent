"""UX-D: guided next-step + soft panel locks (no auto H1/H2/H3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.soft_orchestration import (
    next_step_guide,
    panel_is_unlocked,
    panel_prerequisites_met,
)
from core.lifecycle import distinguish_status

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"


def test_empty_state_guides_initialize_and_locks_later_panels():
    guide = next_step_guide(None)
    assert guide.action_kind == "initialize"
    assert guide.panel_id is None
    assert guide.gate_name is None
    assert not panel_prerequisites_met("problem", None)
    assert not panel_is_unlocked("problem", None, override=False)
    assert panel_is_unlocked("problem", None, override=True)
    assert not panel_is_unlocked("modeling", None, override=False)
    assert not panel_is_unlocked("paper", None, override=False)


def test_initialized_guides_problem_analyst():
    state = {
        "run_id": "run_1",
        "project_id": "demo",
        "workspace_phases": {"project_initialized": "yes"},
    }
    guide = next_step_guide(state)
    assert guide.action_kind == "run_panel"
    assert guide.panel_id == "problem"
    assert panel_is_unlocked("problem", state, override=False)
    assert not panel_is_unlocked("literature", state, override=False)


def test_h1_pending_is_human_gate_never_auto():
    state = {
        "run_id": "run_2",
        "project_id": "demo",
        "workspace_phases": {
            "project_initialized": "yes",
            "independent_eda": "done",
            "literature_evidence": "recorded",
        },
        "problem_specification": {"problem_id": "p", "title": "t"},
        "eda_report": {"report_id": "eda"},
        "evidence_report": {"report_id": "ev"},
        "research_proposal": {"proposal_id": "rp", "candidates": [{"candidate_id": "cand_1"}]},
        "approval_status": {"h1": "pending"},
        "decision_report": {"h1": {"status": "pending"}},
    }
    guide = next_step_guide(state)
    assert guide.action_kind == "human_gate"
    assert guide.gate_name == "H1"
    assert panel_is_unlocked("h1", state, override=False)
    assert not panel_is_unlocked("modeling", state, override=False)
    # Override opens soft UI lock but hard modeling gate remains separate.
    assert panel_is_unlocked("modeling", state, override=True)


def test_h1_approved_guides_modeling_soft_unlock():
    state = {
        "run_id": "run_3",
        "project_id": "demo",
        "workspace_phases": {
            "project_initialized": "yes",
            "independent_eda": "done",
            "literature_evidence": "recorded",
            "h1": "approved",
        },
        "problem_specification": {"problem_id": "p", "title": "t"},
        "eda_report": {"report_id": "eda"},
        "evidence_report": {"report_id": "ev"},
        "research_proposal": {"proposal_id": "rp"},
        "approval_status": {"h1": "approved"},
        "decision_report": {"h1": {"status": "approved"}},
    }
    guide = next_step_guide(state)
    assert guide.panel_id == "modeling"
    assert guide.action_kind == "run_panel"
    assert guide.gate_name is None
    assert panel_is_unlocked("modeling", state, override=False)
    assert not panel_is_unlocked("h2", state, override=False)
    board = distinguish_status(state)
    assert "H1 approved" in board["research_task"]
    assert "joint analysis / strategy modeling not implemented" not in board["research_task"]


def test_h3_approved_is_complete():
    state = {
        "run_id": "run_4",
        "project_id": "demo",
        "workspace_phases": {
            "project_initialized": "yes",
            "independent_eda": "done",
            "literature_evidence": "recorded",
            "h1": "approved",
            "strategy_modeling": "experiment_recorded",
            "h2": "approved",
            "paper_latex": "h3_approved",
            "h3": "approved",
        },
        "problem_specification": {"problem_id": "p", "title": "t"},
        "eda_report": {"report_id": "eda"},
        "evidence_report": {"report_id": "ev"},
        "research_proposal": {"proposal_id": "rp"},
        "paper_outline": {"outline_id": "out"},
        "approval_status": {"h1": "approved", "h2": "approved", "h3": "approved"},
        "decision_report": {
            "h1": {"status": "approved"},
            "h2": {"status": "approved"},
            "h3": {"status": "approved"},
            "experiment": {
                "report_id": "exp",
                "latest_run_id": "run_exp",
                "runs": [
                    {"run_id": "run_exp", "status": "completed", "metrics": {"sharpe": 1.0}}
                ],
            },
            "validation": {"report_id": "val"},
            "paper": {"package_id": "pkg"},
            "e2e_gate": {"e2e_allowed": True},
        },
    }
    guide = next_step_guide(state)
    assert guide.action_kind == "complete"
    assert guide.gate_name is None


def test_apptest_shows_guided_next_and_soft_locks_without_override():
    at = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    assert not at.exception
    texts = "\n".join(
        [
            *(str(x.value) for x in at.subheader),
            *(str(x.value) for x in at.info),
            *(str(x.value) for x in at.markdown),
            *(str(x.label) for x in at.button),
            *(str(x.label) for x in at.checkbox),
        ]
    )
    assert "Guided next step" in texts
    assert "Initialize the research project" in texts or "Go to Initialize project" in texts
    assert "Unlock all panels (power user)" in texts
    # Soft-locked stubs for later stages on cold load.
    assert "Soft-locked until" in texts
    # Problem Analyst run button should not appear until project init / unlock.
    assert all(b.label != "Analyze problem" for b in at.button)


def test_apptest_power_user_override_reveals_problem_analyst():
    at = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    assert not at.exception
    unlock = next(
        c
        for c in at.checkbox
        if c.label == "Unlock all panels (power user)" or "power user" in c.label.lower()
    )
    at = unlock.check().run()
    assert not at.exception
    assert any(b.label == "Analyze problem" for b in at.button)
