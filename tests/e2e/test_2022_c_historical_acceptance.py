"""Phase 9 — offline 2022 MCM C historical E2E acceptance (CI-safe)."""

from __future__ import annotations

from pathlib import Path

import pytest

from e2e.acceptance_facts import ACCEPTANCE_FACTS_2022_C
from e2e.harness import run_2022_c_historical_e2e
from e2e.human_gates import GATE_PRODUCT_VS_HARNESS
from modeling.gate import modeling_allowed
from paper.gate import assert_e2e_allowed, e2e_allowed
from schemas.e2e import E2EAcceptanceReport
from schemas.paper import H3Decision
from schemas.research import H1Decision
from schemas.validation import H2Decision
from tools.problem_spec_2022_c import load_2022_c_fixture
from validation.gate import paper_allowed


def test_gate_product_vs_harness_docs_cover_all_gates():
    assert set(GATE_PRODUCT_VS_HARNESS) == {"H1", "H2", "H3"}
    assert "harness" in GATE_PRODUCT_VS_HARNESS["H1"].lower()
    assert "product" in GATE_PRODUCT_VS_HARNESS["H3"].lower()


def test_full_offline_2022_c_e2e_passes(tmp_path: Path):
    result = run_2022_c_historical_e2e(projects_root=tmp_path / "projects")
    report = result.report
    state = result.state

    assert isinstance(report, E2EAcceptanceReport)
    assert report.overall_passed is True
    assert report.e2e_allowed is True
    assert report.problem_id == "2022_mcm_c"
    assert report.h1_auto_approve is False
    assert report.h2_auto_approve is False
    assert report.h3_auto_approve is False
    assert report.live_llm_used is False
    assert report.live_retrieval_used is False
    assert report.live_trading_api_used is False
    assert report.citation_invented is False
    assert report.product_ui_gates_remain_human_only is True

    assert len(report.steps) == 8
    assert all(step.status == "passed" for step in report.steps)
    assert {g.gate for g in report.gate_records} == {"H1", "H2", "H3"}
    assert all(g.harness_simulated_human for g in report.gate_records)
    assert all(g.auto_approved is False for g in report.gate_records)
    assert all(c.passed for c in report.fact_checks)

    assert state["approval_status"]["h1"] == "approved"
    assert state["approval_status"]["h2"] == "approved"
    assert state["approval_status"]["h3"] == "approved"
    assert e2e_allowed(state) is True
    assert paper_allowed(state) is True
    assert modeling_allowed(state) is True
    assert_e2e_allowed(state)

    harness = (state.get("decision_report") or {}).get("e2e_harness") or {}
    assert harness.get("product_ui_gates_remain_human_only") is True
    assert (state.get("workspace_phases") or {}).get("e2e_acceptance") == "passed"
    # Must not silently complete the research task / claim merge readiness.
    assert state.get("lifecycle") != "research_task_complete"

    # Golden facts catalogue is the source of expected cash / costs.
    assert ACCEPTANCE_FACTS_2022_C["initial_cash_usd"] == 1000.0
    assert ACCEPTANCE_FACTS_2022_C["alpha_gold"] == 0.01
    assert ACCEPTANCE_FACTS_2022_C["alpha_bitcoin"] == 0.02


def test_e2e_blocked_until_h3_even_with_paper(tmp_path: Path):
    """Partial walk: stop after paper attach — E2E must stay blocked without H3."""
    from agents.modeling_experiment import run_modeling_experiment
    from agents.paper_planner import run_paper_planner
    from agents.problem_analyst import analyze_problem
    from agents.research_strategy import synthesize_research_proposal
    from agents.validation_sensitivity import run_validation_sensitivity
    from core.project_store import LocalProjectStore
    from e2e.human_gates import apply_harness_h1_approval, apply_harness_h2_approval
    from tools.experiment_persistence import persist_experiment_into_state
    from tools.paper_persistence import persist_paper_into_state
    from tools.research_persistence import persist_research_proposal_into_state
    from tools.validation_persistence import persist_validation_into_state

    store = LocalProjectStore(tmp_path / "projects")
    boot = {
        "project_id": "mcm-c-e2e-2022",
        "project_name": "partial",
        "project_status": "initialized",
        "lifecycle": "data_analysis_done",
        "uploaded_files": [],
        "citations": [],
        "model_artifacts": [],
        "experiment_logs": [],
        "workspace_phases": {},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    _p, run, state = store.save_project_state(
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=boot,
        input_signature="sig-partial",
        note="boot",
    )
    state = dict(state)
    state["run_id"] = run.run_id

    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    state["problem_specification"] = spec.model_dump(mode="json")
    state = persist_research_proposal_into_state(
        store,
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=state,
        input_signature="sig-partial",
        proposal=proposal,
    )
    state, _ = apply_harness_h1_approval(
        store,
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=state,
        input_signature="sig-partial",
        proposal=proposal,
        selected_candidate_id=proposal.recommended_candidate_id,
    )
    experiment = run_modeling_experiment(
        state=state, problem_specification=spec, proposal=proposal
    )
    state = persist_experiment_into_state(
        store,
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=state,
        input_signature="sig-partial",
        report=experiment,
    )
    validation = run_validation_sensitivity(
        state=state, problem_specification=spec, proposal=proposal, use_llm=False
    )
    state = persist_validation_into_state(
        store,
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=state,
        input_signature="sig-partial",
        report=validation,
    )
    state, _ = apply_harness_h2_approval(
        store,
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=state,
        input_signature="sig-partial",
        report=validation,
    )
    package = run_paper_planner(state=state, problem_specification=spec)
    state = persist_paper_into_state(
        store,
        project_id="mcm-c-e2e-2022",
        project_name="partial",
        state=state,
        input_signature="sig-partial",
        package=package,
    )
    assert state["approval_status"]["h3"] == "pending"
    assert e2e_allowed(state) is False
    with pytest.raises(PermissionError):
        assert_e2e_allowed(state)


def test_schemas_reject_auto_approved_h_gates():
    with pytest.raises(Exception):
        H1Decision(
            decision_id="h1d_bad",
            status="approved",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            notes="nope",
            decided_by="human",
            auto_approved=True,
            decided_at_utc="2026-01-01T00:00:00Z",
        )
    with pytest.raises(Exception):
        H2Decision(
            decision_id="h2d_bad",
            status="approved",
            validation_report_id="vrep_x",
            baseline_run_id="erun_x",
            proposal_id="prop_x",
            notes="nope",
            decided_by="human",
            auto_approved=True,
            decided_at_utc="2026-01-01T00:00:00Z",
        )
    with pytest.raises(Exception):
        H3Decision(
            decision_id="h3d_bad",
            status="approved",
            package_id="ppkg_x",
            outline_id="pout_x",
            notes="nope",
            decided_by="human",
            auto_approved=True,
            decided_at_utc="2026-01-01T00:00:00Z",
        )


def test_optional_cli_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from e2e.cli import main

    code = main(["--projects-root", str(tmp_path / "cli-projects")])
    assert code == 0
