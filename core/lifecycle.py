"""Honest project lifecycle labels for the Research Lab.

Intake and dataset recording remain Phase 1 foundations. Phases 6–8
(modeling, validation/H2, paper/H3) advance via human gates — this module
only labels status and never auto-approves H1/H2/H3.
"""

from __future__ import annotations

from typing import Any

from modeling.gate import read_h1_status
from paper.gate import read_h3_status
from schemas.persistence import ProjectLifecycle
from validation.gate import has_experiment_results, read_h2_status

LIFECYCLE_CREATED: ProjectLifecycle = "created"
LIFECYCLE_PROJECT_INITIALIZED: ProjectLifecycle = "project_initialized"
LIFECYCLE_DATASETS_RECORDED: ProjectLifecycle = "datasets_recorded"
LIFECYCLE_DATA_ANALYSIS_DONE: ProjectLifecycle = "data_analysis_done"
LIFECYCLE_RESEARCH_TASK_COMPLETE: ProjectLifecycle = "research_task_complete"

ANALYSIS_NOT_STARTED = "not_started"
ANALYSIS_DATA_DONE = "data_analysis_done"
ANALYSIS_RESEARCH_COMPLETE = "research_task_complete"

RECOMPUTE_PROMPT = (
    "Inputs changed (problem text, files, project ID, or model config). "
    "Previous approvals and derived results are stale — recompute before trusting them."
)


def lifecycle_from_state(state: dict[str, Any] | None) -> ProjectLifecycle:
    """Derive lifecycle from a ResearchState-like mapping."""
    if not state:
        return LIFECYCLE_CREATED
    explicit = state.get("lifecycle")
    if explicit in {
        LIFECYCLE_CREATED,
        LIFECYCLE_PROJECT_INITIALIZED,
        LIFECYCLE_DATASETS_RECORDED,
        LIFECYCLE_DATA_ANALYSIS_DONE,
        LIFECYCLE_RESEARCH_TASK_COMPLETE,
    }:
        return explicit  # type: ignore[return-value]
    analysis = state.get("analysis_status")
    if analysis == ANALYSIS_RESEARCH_COMPLETE:
        return LIFECYCLE_RESEARCH_TASK_COMPLETE
    if analysis == ANALYSIS_DATA_DONE or state.get("eda_report"):
        return LIFECYCLE_DATA_ANALYSIS_DONE
    files = state.get("uploaded_files") or []
    if files:
        return LIFECYCLE_DATASETS_RECORDED
    if state.get("project_status") in {"initialized", "created"} or state.get("project_id"):
        return LIFECYCLE_PROJECT_INITIALIZED
    return LIFECYCLE_CREATED


def _research_task_label(state: dict[str, Any] | None, lifecycle: ProjectLifecycle) -> str:
    """Honest research-progress string aligned with Phases 6–8 gates."""
    if lifecycle == LIFECYCLE_RESEARCH_TASK_COMPLETE:
        return "complete"

    h1 = read_h1_status(state)
    h2 = read_h2_status(state)
    h3 = read_h3_status(state)

    if h3 == "approved":
        return "H3 approved — E2E / export may advance (human-gated)"
    if h3 == "pending":
        return "Paper package pending human H3 approval"
    if h3 == "revision_requested":
        return "H3 revision requested — update paper package"
    if h3 == "rejected":
        return "H3 rejected — paper package blocked"
    if h2 == "approved":
        return "H2 approved — Paper / H3 available"
    if h2 == "pending":
        return "Validation pending human H2 approval"
    if h2 == "revision_requested":
        return "H2 revision requested — update validation"
    if h2 == "rejected":
        return "H2 rejected — paper blocked"
    if has_experiment_results(state):
        return "Modeling recorded — run Validation / H2 (human gate)"
    if h1 == "approved":
        return "H1 approved — Modeling & Experiment available"
    if h1 == "pending":
        return "Research proposal pending human H1 approval"
    if h1 == "revision_requested":
        return "H1 revision requested — revise research proposal"
    if h1 == "rejected":
        return "H1 rejected — modeling blocked"
    if lifecycle in {LIFECYCLE_DATA_ANALYSIS_DONE, LIFECYCLE_DATASETS_RECORDED}:
        return "in progress — continue Problem → EDA → Literature → H1 (human gates)"
    if lifecycle in {LIFECYCLE_PROJECT_INITIALIZED, LIFECYCLE_CREATED}:
        return "not started — initialize & analyze before H1/H2/H3"
    return "not started — initialize & analyze before H1/H2/H3"


def distinguish_status(state: dict[str, Any] | None) -> dict[str, str]:
    """Human-readable status board: init vs data analysis vs research progress."""
    lifecycle = lifecycle_from_state(state)
    return {
        "project_init": (
            "success"
            if lifecycle
            in {
                LIFECYCLE_PROJECT_INITIALIZED,
                LIFECYCLE_DATASETS_RECORDED,
                LIFECYCLE_DATA_ANALYSIS_DONE,
                LIFECYCLE_RESEARCH_TASK_COMPLETE,
            }
            else "not started"
        ),
        "data_analysis": (
            "done"
            if lifecycle in {LIFECYCLE_DATA_ANALYSIS_DONE, LIFECYCLE_RESEARCH_TASK_COMPLETE}
            else ("datasets recorded" if lifecycle == LIFECYCLE_DATASETS_RECORDED else "not done")
        ),
        "research_task": _research_task_label(state, lifecycle),
        "lifecycle": lifecycle,
    }


def mark_data_analysis_done(state: dict[str, Any]) -> dict[str, Any]:
    """Promote state after an approved independent EDA (still not research-complete)."""
    updated = dict(state)
    updated["analysis_status"] = ANALYSIS_DATA_DONE
    updated["lifecycle"] = LIFECYCLE_DATA_ANALYSIS_DONE
    return updated
