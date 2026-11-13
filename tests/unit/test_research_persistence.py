"""Phase 5 research / H1 persistence + sanitize checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.debate_critic import critique_research_proposal
from agents.literature_evidence import gather_literature_evidence
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from core.project_store import LocalProjectStore
from modeling.gate import modeling_allowed, modeling_gate_status
from schemas.persistence import sanitize_state_for_persistence
from schemas.research import H1Decision
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.research_persistence import (
    build_h1_decision,
    compact_research_proposal,
    persist_h1_decision_into_state,
    persist_research_proposal_into_state,
)


@pytest.fixture
def proposal_and_critique():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    evidence = gather_literature_evidence(problem_specification=spec, use_live=False)
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        evidence_report=evidence,
        use_llm=False,
    )
    critique = critique_research_proposal(
        proposal=proposal,
        problem_specification=spec,
        evidence_report=evidence,
        use_llm=False,
    )
    return proposal, critique


def _boot_state(store: LocalProjectStore) -> dict:
    state = {
        "project_id": "mcm-c-demo",
        "project_name": "MCM C Demo Project",
        "project_status": "initialized",
        "lifecycle": "data_analysis_done",
        "analysis_status": "data_analysis_done",
        "uploaded_files": [],
        "citations": [],
        "workspace_phases": {},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    _project, run, boot = store.save_project_state(
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase5-test",
        note="bootstrap",
    )
    boot = dict(boot)
    boot["run_id"] = run.run_id
    return boot


def test_compact_proposal_is_persistence_safe(proposal_and_critique):
    proposal, _critique = proposal_and_critique
    compact = compact_research_proposal(proposal)
    assert compact["invented_sources"] is False
    sanitize_state_for_persistence(
        {
            "project_id": "mcm-c-demo",
            "project_name": "MCM C Demo Project",
            "project_status": "initialized",
            "lifecycle": "project_initialized",
            "uploaded_files": [],
            "research_proposal": compact,
        }
    )


def test_persist_proposal_sets_h1_pending_and_blocks_modeling(
    tmp_path: Path, proposal_and_critique
):
    proposal, critique = proposal_and_critique
    store = LocalProjectStore(root=tmp_path / "projects")
    boot = _boot_state(store)
    saved = persist_research_proposal_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=boot,
        input_signature="sig-phase5-test",
        proposal=proposal,
        critique=critique,
    )
    assert saved.get("research_proposal")
    assert saved["approval_status"]["h1"] == "pending"
    assert saved["workspace_phases"]["h1"] == "pending"
    assert saved["workspace_phases"]["strategy_modeling"] == "blocked_until_h1"
    assert modeling_allowed(saved) is False
    gate = modeling_gate_status(saved)
    assert gate.modeling_allowed is False
    assert gate.reason == "h1_pending"
    assert saved.get("lifecycle") != "research_task_complete"
    assert saved.get("disagreement_log")


def test_build_h1_decision_accepts_compact_proposal_dict(proposal_and_critique):
    """UI reloads persisted proposal dicts that include report_version."""
    proposal, critique = proposal_and_critique
    compact = compact_research_proposal(proposal)
    assert "report_version" in compact
    decision = build_h1_decision(
        status="approved",
        proposal=compact,
        selected_candidate_id=proposal.recommended_candidate_id,
        notes="Approve from compact session payload.",
        critique_id=critique.critique_id,
    )
    assert decision.status == "approved"
    assert decision.auto_approved is False


def test_human_approve_unlocks_gate_but_not_phase6(
    tmp_path: Path, proposal_and_critique
):
    proposal, critique = proposal_and_critique
    store = LocalProjectStore(root=tmp_path / "projects")
    boot = _boot_state(store)
    pending = persist_research_proposal_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=boot,
        input_signature="sig-phase5-test",
        proposal=proposal,
        critique=critique,
    )
    decision = build_h1_decision(
        status="approved",
        proposal=proposal,
        selected_candidate_id=proposal.recommended_candidate_id,
        notes="Human approved after reviewing critique.",
        critique_id=critique.critique_id,
    )
    assert decision.auto_approved is False
    assert decision.decided_by == "human"
    saved = persist_h1_decision_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=pending,
        input_signature="sig-phase5-test",
        decision=decision,
    )
    assert saved["approval_status"]["h1"] == "approved"
    assert modeling_allowed(saved) is True
    assert saved["workspace_phases"]["strategy_modeling"] == "h1_approved_phase6_pending"
    assert saved.get("lifecycle") != "research_task_complete"
    assert saved["decision_report"]["h1"]["auto_approved"] is False


def test_request_revision_keeps_modeling_blocked(
    tmp_path: Path, proposal_and_critique
):
    proposal, critique = proposal_and_critique
    store = LocalProjectStore(root=tmp_path / "projects")
    boot = _boot_state(store)
    pending = persist_research_proposal_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=boot,
        input_signature="sig-phase5-test",
        proposal=proposal,
        critique=critique,
    )
    decision = build_h1_decision(
        status="revision_requested",
        proposal=proposal,
        selected_candidate_id=None,
        notes="Please address blocking evidence gaps.",
        critique_id=critique.critique_id,
    )
    saved = persist_h1_decision_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=pending,
        input_signature="sig-phase5-test",
        decision=decision,
    )
    assert saved["approval_status"]["h1"] == "revision_requested"
    assert modeling_allowed(saved) is False
    assert saved["workspace_phases"]["strategy_modeling"] == "blocked_until_h1"


def test_refuse_auto_approved_h1_payload():
    with pytest.raises(ValidationError):
        H1Decision.model_validate(
            {
                "decision_id": "h1d_auto",
                "status": "approved",
                "proposal_id": "prop_x",
                "selected_candidate_id": "cand_x",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )
