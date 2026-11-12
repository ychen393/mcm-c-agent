from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    project_id: str
    project_name: str
    project_status: str
    current_stage: str
    run_id: str
    lifecycle: str
    analyst_entry_lifecycle: str
    foundation_input_signature: str
    problem_revision_notes: str
    data_resume: str
    problem_text: str
    uploaded_files: list[dict[str, Any]]
    dataset_metadata: dict[str, Any]
    analysis_status: str
    workspace_phases: dict[str, str]
    problem_specification: dict[str, Any]
    eda_report: dict[str, Any]
    research_proposal: dict[str, Any]
    disagreement_log: list[dict[str, Any]]
    decision_report: dict[str, Any]
    model_artifacts: list[dict[str, Any]]
    validation_report: dict[str, Any]
    paper_outline: dict[str, Any]
    latex_source: str
    review_report: dict[str, Any]
    approval_status: dict[str, str]
    citations: list[dict[str, Any]]
    experiment_logs: list[dict[str, Any]]
    ai_usage_logs: list[dict[str, Any]]
    errors: list[dict[str, Any]]


def new_research_state(project_id: str, project_name: str) -> ResearchState:
    return {
        "project_id": project_id,
        "project_name": project_name,
        "project_status": "created",
        "current_stage": "intake",
        "analysis_status": "not_started",
        "lifecycle": "created",
        "uploaded_files": [],
        "disagreement_log": [],
        "model_artifacts": [],
        "approval_status": {},
        "citations": [],
        "experiment_logs": [],
        "ai_usage_logs": [],
        "errors": [],
    }
