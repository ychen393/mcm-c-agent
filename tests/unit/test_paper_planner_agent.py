"""Phase 8 paper planner agent entry tests."""

from __future__ import annotations

import pytest

from agents.literature_evidence import gather_literature_evidence
from agents.paper_planner import paper_planner_status, run_paper_planner
from agents.problem_analyst import analyze_problem
from tools.problem_spec_2022_c import load_2022_c_fixture


def _h2_state():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    evidence = gather_literature_evidence(
        problem_specification=spec,
        use_live=False,
    )
    state = {
        "problem_specification": spec.model_dump(mode="json"),
        "evidence_report": evidence.model_dump(mode="json"),
        "validation_report": {
            "report_id": "vrep_agent",
            "baseline_run_id": "erun_agent",
            "proposal_id": "prop_agent",
            "scenarios": [{"scenario_id": "scn_a"}],
        },
        "research_proposal": {"proposal_id": "prop_agent"},
        "approval_status": {"h1": "approved", "h2": "approved"},
    }
    return state, spec


def test_status_never_auto_approves():
    status = paper_planner_status()
    assert status["phase"] == 8
    assert status["h1_auto_approve"] is False
    assert status["h2_auto_approve"] is False
    assert status["h3_auto_approve"] is False
    assert status["requires_h2_approved"] is True
    assert status["e2e_requires_h3_approved"] is True
    assert status["pdf_compile_required_for_ci"] is False
    assert status["llm_outline_executes_live_calls"] is False


def test_run_refused_without_h2():
    state, spec = _h2_state()
    state["approval_status"]["h2"] = "pending"
    with pytest.raises(PermissionError):
        run_paper_planner(state=state, problem_specification=spec)


def test_run_builds_package_when_h2_approved():
    state, spec = _h2_state()
    package = run_paper_planner(
        state=state,
        problem_specification=spec,
        use_llm=True,  # stub only
        attempt_pdf_compile=False,
    )
    assert package.paper_allowed is True
    assert package.invented_citations is False
    assert package.outline.sections
    assert package.latex is not None
    assert package.review is not None
    assert package.outline.llm_attempted is True
    assert package.outline.llm_note
