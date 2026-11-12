"""Validation / Sensitivity Agent (Phase 7).

Default path is CI-safe deterministic sensitivity over Phase 6 fixture
experiment outputs. Runs are refused unless ResearchState shows human H1
approval **and** available experiment results. Optional LLM critique stays a
non-executing stub. H2 is never auto-approved; Paper / LaTeX stays Phase 8.
"""

from __future__ import annotations

import os
from typing import Any

from core.config import Settings, get_settings
from schemas.problem_specification import ProblemSpecification
from schemas.research import ResearchProposal
from schemas.validation import ValidationReport
from validation.gate import (
    assert_validation_allowed,
    resolve_baseline_run_id,
    validation_gate_status,
)
from validation.runner import LLM_UNAVAILABLE_NOTE, PROMPT_VERSION, execute_validation_report


def _llm_enabled(settings: Settings | None, use_llm: bool | None) -> bool:
    if use_llm is not None:
        return bool(use_llm)
    if settings is not None:
        return bool(settings.validation_use_llm)
    env = os.getenv("VALIDATION_USE_LLM", "").strip().lower()
    return env in {"1", "true", "yes", "on"}


def _as_proposal(
    proposal: ResearchProposal | dict[str, Any] | None,
) -> ResearchProposal | None:
    if proposal is None:
        return None
    if isinstance(proposal, ResearchProposal):
        return proposal
    if isinstance(proposal, dict) and proposal:
        return ResearchProposal.model_validate(proposal)
    return None


def _experiment_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        raise ValueError("ResearchState is required for validation.")
    decision = state.get("decision_report") or {}
    if isinstance(decision, dict):
        experiment = decision.get("experiment")
        if isinstance(experiment, dict) and experiment:
            return experiment
    logs = state.get("experiment_logs") or []
    if isinstance(logs, list):
        for entry in reversed(logs):
            if (
                isinstance(entry, dict)
                and entry.get("run_id")
                and entry.get("status") == "completed"
                and entry.get("metrics")
            ):
                return {
                    "report_id": None,
                    "latest_run_id": entry.get("run_id"),
                    "runs": [entry],
                    "proposal_id": entry.get("proposal_id"),
                    "selected_candidate_id": entry.get("selected_candidate_id"),
                }
    raise ValueError("No Phase 6 experiment results available for validation.")


def _selected_candidate_id(
    state: dict[str, Any] | None,
    proposal: ResearchProposal | None,
    experiment: dict[str, Any],
    override: str | None,
) -> str:
    if override:
        return override
    if experiment.get("selected_candidate_id"):
        return str(experiment["selected_candidate_id"])
    if state:
        decision = state.get("decision_report") or {}
        if isinstance(decision, dict):
            h1 = decision.get("h1") or {}
            if isinstance(h1, dict) and h1.get("selected_candidate_id"):
                return str(h1["selected_candidate_id"])
    if proposal and proposal.recommended_candidate_id:
        return proposal.recommended_candidate_id
    if proposal and proposal.candidates:
        return proposal.candidates[0].candidate_id
    raise ValueError("No candidate available for validation.")


def _proposal_id(
    state: dict[str, Any] | None,
    proposal: ResearchProposal | None,
    experiment: dict[str, Any],
) -> str:
    if experiment.get("proposal_id"):
        return str(experiment["proposal_id"])
    if proposal:
        return proposal.proposal_id
    if state:
        raw = state.get("research_proposal") or {}
        if isinstance(raw, dict) and raw.get("proposal_id"):
            return str(raw["proposal_id"])
    raise ValueError("proposal_id is required for validation.")


def validation_sensitivity_status(settings: Settings | None = None) -> dict[str, Any]:
    """Status advertisement for UI / tests."""
    cfg = settings or get_settings()
    return {
        "phase": 7,
        "agent": "validation_sensitivity",
        "prompt_version": PROMPT_VERSION,
        "default_strategy": "deterministic_fixture",
        "live_trading_apis": False,
        "h1_auto_approve": False,
        "h2_auto_approve": False,
        "requires_h1_approved": True,
        "requires_experiment_results": True,
        "paper_requires_h2_approved": True,
        "llm_critique_default": bool(cfg.validation_use_llm),
        "llm_critique_executes_live_calls": False,
        "llm_note": LLM_UNAVAILABLE_NOTE,
    }


def run_validation_sensitivity(
    *,
    state: dict[str, Any] | None,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    proposal: ResearchProposal | dict[str, Any] | None = None,
    selected_candidate_id: str | None = None,
    use_llm: bool | None = None,
    settings: Settings | None = None,
) -> ValidationReport:
    """Run deterministic validation when H1 + experiments allow; else PermissionError."""
    assert_validation_allowed(state)
    gate = validation_gate_status(state)

    experiment = _experiment_from_state(state)
    proposal_model = _as_proposal(proposal)
    if proposal_model is None and state:
        proposal_model = _as_proposal(state.get("research_proposal"))

    candidate_id = _selected_candidate_id(
        state, proposal_model, experiment, selected_candidate_id
    )
    proposal_id = _proposal_id(state, proposal_model, experiment)
    cfg = settings or get_settings()
    llm = _llm_enabled(cfg, use_llm)

    spec = problem_specification
    if spec is None and state:
        spec = state.get("problem_specification")

    problem_id = None
    if isinstance(spec, ProblemSpecification):
        problem_id = spec.problem_id
    elif isinstance(spec, dict):
        problem_id = spec.get("problem_id")

    report = execute_validation_report(
        experiment=experiment,
        proposal_id=proposal_id,
        selected_candidate_id=candidate_id,
        problem_specification=spec,
        problem_id=str(problem_id) if problem_id else None,
        llm_enabled=llm,
    )

    notes = list(report.analysis_notes)
    notes.append(f"validation_gate.reason={gate.reason}")
    notes.append(f"baseline_from_gate={resolve_baseline_run_id(state)}")
    return report.model_copy(update={"analysis_notes": notes[:32]})
