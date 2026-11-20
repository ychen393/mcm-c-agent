"""Revising H1 may not preserve old modeling results or old H2/H3 approvals."""
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from core.project_store import LocalProjectStore
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.research_persistence import persist_research_proposal_into_state


def test_new_human_revised_research_proposal_invalidates_downstream(tmp_path):
    spec=analyze_problem(load_2022_c_fixture(),use_llm=False)
    proposal=synthesize_research_proposal(problem_specification=spec,use_llm=False)
    store=LocalProjectStore(tmp_path/"projects")
    state={
        "project_id":"revision-risk-check",
        "project_name":"Revision review",
        "lifecycle":"data_analysis_done",
        "analysis_status":"data_analysis_done",
        "uploaded_files":[],
        "model_artifacts":[{"artifact_id":"old-model"}],
        "experiment_logs":[{"kind":"old-experiment"}],
        "validation_report":{"report_id":"old-validation"},
        "paper_outline":{"outline_id":"old-paper"},
        "latex_source":"old latex",
        "workspace_phases":{"strategy_modeling":"recorded","validation_sensitivity":"done",
                            "paper_latex":"recorded","h2":"approved","h3":"approved"},
        "approval_status":{"h1":"revision_requested","h2":"approved","h3":"approved"},
        "decision_report":{
            "experiment":{"strategy":"obsolete"},
            "h1":{"status":"revision_requested","notes":"Please update the cost-aware method"},
            "h2":{"status":"approved"},
            "h3":{"status":"approved"},
        },
        "citations":[],"errors":[],"data_resume":"reupload_required",
    }
    _project,run,recorded=store.save_project_state(
        project_id=state["project_id"],project_name=state["project_name"],
        state=state,input_signature="feedback-test",note="init")
    recorded=dict(recorded)
    recorded["run_id"]=run.run_id
    saved=persist_research_proposal_into_state(
        store,project_id=state["project_id"],project_name=state["project_name"],
        state=recorded,input_signature="feedback-test",proposal=proposal,
        review_record={
            "feedback":"Please update gold market day handling and BTC commission.",
            "before":"Earlier test approach",
            "after":"Revised cost-aware plan",
            "changes_made":"Added explicit market calendar checks",
            "mode":"two_live_llm_calls",
        },
    )
    assert saved["approval_status"]["h1"]=="pending"
    assert "h2" not in saved["approval_status"]
    assert "h3" not in saved["approval_status"]
    assert not saved.get("validation_report")
    assert not saved.get("paper_outline")
    assert not saved.get("latex_source")
    assert saved["model_artifacts"]==[]
    assert saved["experiment_logs"]==[]
    assert "experiment" not in saved["decision_report"]
    assert saved["decision_report"]["revision_history"][-1]["feedback"].startswith("Please update")
    assert saved["workspace_phases"].get("h2") is None
    assert saved["workspace_phases"].get("paper_latex") is None
