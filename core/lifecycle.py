"""Honest project lifecycle labels for Phase 1.

Phase 1 can reach project initialization and dataset recording. Independent
EDA and relationship preview live on the Streamlit page. Joint analysis and
a completed research task are not implemented yet.
"""

from __future__ import annotations

from typing import Any

from schemas.persistence import ProjectLifecycle

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


def distinguish_status(state: dict[str, Any] | None) -> dict[str, str]:
    """Human-readable status board: init vs data analysis vs research complete."""
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
        "research_task": (
            "complete"
            if lifecycle == LIFECYCLE_RESEARCH_TASK_COMPLETE
            else "NOT COMPLETE — joint analysis / strategy modeling not implemented"
        ),
        "lifecycle": lifecycle,
    }


def mark_data_analysis_done(state: dict[str, Any]) -> dict[str, Any]:
    """Promote state after an approved independent EDA (still not research-complete)."""
    updated = dict(state)
    updated["analysis_status"] = ANALYSIS_DATA_DONE
    updated["lifecycle"] = LIFECYCLE_DATA_ANALYSIS_DONE
    return updated
