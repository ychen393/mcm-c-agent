"""Sanitize Modeling & Experiment results into ResearchState (Phase 6).

Persisted payloads must pass Phase 1 sanitize_state_for_persistence rules.
Runs / attaches are refused unless human H1 is approved (modeling gate).
"""

from __future__ import annotations

from typing import Any

from core.project_store import ProjectStore
from modeling.gate import assert_modeling_allowed, modeling_gate_status
from schemas.experiment import ExperimentReport, ExperimentRun
from schemas.persistence import assert_safe_for_persistence

EXPERIMENT_REPORT_VERSION = "experiment_report_1.0"
EXPERIMENT_LOG_VERSION = "experiment_log_1.0"


def as_experiment_run(run: ExperimentRun | dict[str, Any]) -> ExperimentRun:
    if isinstance(run, ExperimentRun):
        return run
    from tools.research_persistence import strip_persistence_only

    return ExperimentRun.model_validate(strip_persistence_only(run))


def as_experiment_report(report: ExperimentReport | dict[str, Any]) -> ExperimentReport:
    if isinstance(report, ExperimentReport):
        return report
    from tools.research_persistence import strip_persistence_only

    return ExperimentReport.model_validate(strip_persistence_only(report))


def compact_experiment_run(run: ExperimentRun | dict[str, Any]) -> dict[str, Any]:
    model = as_experiment_run(run)
    if model.invented_results:
        raise ValueError("Refusing to persist invented experiment results.")
    if model.live_trading_api_used:
        raise ValueError("Refusing to persist runs that used live trading APIs.")
    if model.h1_status != "approved":
        raise ValueError("Refusing to persist experiment without h1_status=approved.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = EXPERIMENT_LOG_VERSION
    payload["invented_results"] = False
    payload["live_trading_api_used"] = False
    assert_safe_for_persistence(payload, "experiment_logs")
    return payload


def compact_experiment_report(
    report: ExperimentReport | dict[str, Any],
) -> dict[str, Any]:
    model = as_experiment_report(report)
    if model.invented_results or model.live_trading_api_used:
        raise ValueError("Refusing to persist unsafe experiment report.")
    if not model.h1_approved or not model.modeling_allowed:
        raise ValueError("Refusing to persist experiment report without H1-approved gate.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = EXPERIMENT_REPORT_VERSION
    payload["invented_results"] = False
    payload["live_trading_api_used"] = False
    assert_safe_for_persistence(payload, "decision_report.experiment")
    return payload


def model_artifact_entries_from_run(
    run: ExperimentRun | dict[str, Any],
) -> list[dict[str, Any]]:
    model = as_experiment_run(run)
    entries: list[dict[str, Any]] = []
    for artifact in model.artifacts:
        entry = {
            "artifact_id": artifact.artifact_id,
            "kind": artifact.kind,
            "summary": artifact.summary,
            "payload": artifact.payload,
            "content_sha256": artifact.content_sha256,
            "run_id": model.run_id,
            "proposal_id": model.proposal_id,
            "selected_candidate_id": model.selected_candidate_id,
        }
        assert_safe_for_persistence(entry, "model_artifacts")
        entries.append(entry)
    return entries


def experiment_log_entry_from_run(
    run: ExperimentRun | dict[str, Any],
) -> dict[str, Any]:
    compact = compact_experiment_run(run)
    # Keep logs lean: drop bulky nested artifact payloads (kept in model_artifacts).
    lean = {
        "report_version": EXPERIMENT_LOG_VERSION,
        "run_id": compact["run_id"],
        "status": compact["status"],
        "strategy": compact["strategy"],
        "proposal_id": compact["proposal_id"],
        "selected_candidate_id": compact["selected_candidate_id"],
        "method_family": compact.get("method_family"),
        "h1_status": compact["h1_status"],
        "h1_decision_id": compact.get("h1_decision_id"),
        "params": compact.get("params"),
        "code_refs": compact.get("code_refs"),
        "metrics": compact.get("metrics"),
        "constraints": compact.get("constraints"),
        "started_at_utc": compact.get("started_at_utc"),
        "finished_at_utc": compact.get("finished_at_utc"),
        "analysis_notes": compact.get("analysis_notes"),
        "sandboxed_python_attempted": compact.get("sandboxed_python_attempted"),
        "sandboxed_python_note": compact.get("sandboxed_python_note"),
        "live_trading_api_used": False,
        "invented_results": False,
        "agent_prompt_version": compact.get("agent_prompt_version"),
        "artifact_ids": [a.get("artifact_id") for a in compact.get("artifacts") or []],
    }
    assert_safe_for_persistence(lean, "experiment_logs")
    return lean


def persist_experiment_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    report: ExperimentReport | dict[str, Any],
    note: str = "phase6-modeling-experiment",
) -> dict[str, Any]:
    """Attach sanitized experiment report into project state. Requires H1 approved."""
    assert_modeling_allowed(state)
    model = as_experiment_report(report)
    if not model.runs:
        raise ValueError("Experiment report has no runs to persist.")

    latest = model.runs[-1]
    if model.latest_run_id:
        for run in model.runs:
            if run.run_id == model.latest_run_id:
                latest = run
                break

    compact_report = compact_experiment_report(model)
    log_entry = experiment_log_entry_from_run(latest)
    artifacts = model_artifact_entries_from_run(latest)

    updated = dict(state)
    experiment_logs = list(updated.get("experiment_logs") or [])
    experiment_logs.append(log_entry)
    updated["experiment_logs"] = experiment_logs

    # Replace Phase 6 model artifacts with the latest run's set (keep prior non-matching).
    prior_artifacts = [
        item
        for item in (updated.get("model_artifacts") or [])
        if isinstance(item, dict) and item.get("run_id") != latest.run_id
    ]
    updated["model_artifacts"] = prior_artifacts + artifacts

    decision_report = dict(updated.get("decision_report") or {})
    decision_report["experiment"] = compact_report
    decision_report["modeling_gate"] = modeling_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision_report

    phases = dict(updated.get("workspace_phases") or {})
    phases["strategy_modeling"] = "experiment_recorded"
    phases["modeling_experiment"] = "recorded"
    updated["workspace_phases"] = phases

    # Do not mark research_task_complete, approve H2, or start Phase 8 paper.
    assert_safe_for_persistence(updated, "state")

    _project, run, saved = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=updated,
        input_signature=input_signature,
        note=note,
    )
    saved = dict(saved)
    saved["run_id"] = run.run_id
    saved["data_resume"] = "reupload_required"
    return saved
