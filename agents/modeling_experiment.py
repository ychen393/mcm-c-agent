"""Mathematical Modeling & Experiment Agent (Phase 6).

Default path is CI-safe deterministic backtesting over a synthetic 2022 MCM C
price fixture. Runs are refused unless ResearchState shows human H1 approval.
Optional sandboxed Python stays a non-executing stub. Live trading APIs are
forbidden.
"""

from __future__ import annotations

import os
from typing import Any

from core.config import Settings, get_settings
from modeling.gate import assert_modeling_allowed, modeling_gate_status
from modeling.runner import (
    PROMPT_VERSION,
    SANDBOX_UNAVAILABLE_NOTE,
    execute_experiment_run,
)
from schemas.experiment import ExperimentReport, ExperimentRun
from schemas.problem_specification import ProblemSpecification
from schemas.research import ResearchProposal


def _sandbox_enabled(settings: Settings | None, allow_sandbox: bool | None) -> bool:
    if allow_sandbox is not None:
        return bool(allow_sandbox)
    if settings is not None:
        return bool(settings.modeling_allow_sandboxed_python)
    env = os.getenv("MODELING_ALLOW_SANDBOXED_PYTHON", "").strip().lower()
    return env in {"1", "true", "yes", "on"}


def _as_proposal(
    proposal: ResearchProposal | dict[str, Any] | None,
) -> ResearchProposal | None:
    if proposal is None:
        return None
    if isinstance(proposal, ResearchProposal):
        return proposal
    if isinstance(proposal, dict) and proposal:
        from tools.research_persistence import as_research_proposal

        return as_research_proposal(proposal)
    return None


def _selected_candidate_id(
    state: dict[str, Any] | None,
    proposal: ResearchProposal,
    override: str | None,
) -> str:
    if override:
        return override
    if state:
        decision = state.get("decision_report") or {}
        if isinstance(decision, dict):
            h1 = decision.get("h1") or {}
            if isinstance(h1, dict) and h1.get("selected_candidate_id"):
                return str(h1["selected_candidate_id"])
        # Fallback: recommended on proposal.
    if proposal.recommended_candidate_id:
        return proposal.recommended_candidate_id
    if proposal.candidates:
        return proposal.candidates[0].candidate_id
    raise ValueError("No candidate available for modeling experiment.")


def _h1_decision_id(state: dict[str, Any] | None) -> str | None:
    if not state:
        return None
    decision = state.get("decision_report") or {}
    if isinstance(decision, dict):
        h1 = decision.get("h1") or {}
        if isinstance(h1, dict):
            raw = h1.get("decision_id")
            return str(raw) if raw else None
    return None


def modeling_experiment_status(settings: Settings | None = None) -> dict[str, Any]:
    """Status advertisement for UI / tests."""
    cfg = settings or get_settings()
    return {
        "phase": 6,
        "agent": "modeling_experiment",
        "prompt_version": PROMPT_VERSION,
        "default_strategy": "deterministic_fixture",
        "live_trading_apis": False,
        "h1_auto_approve": False,
        "requires_h1_approved": True,
        "sandboxed_python_default": bool(cfg.modeling_allow_sandboxed_python),
        "sandboxed_python_executes_arbitrary_code": False,
        "sandbox_note": SANDBOX_UNAVAILABLE_NOTE,
    }


def run_modeling_experiment(
    *,
    state: dict[str, Any] | None,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    proposal: ResearchProposal | dict[str, Any] | None = None,
    selected_candidate_id: str | None = None,
    strategy_id: str | None = None,
    lookback_days: int = 3,
    rebalance_every_n_days: int = 5,
    allow_sandboxed_python: bool | None = None,
    settings: Settings | None = None,
) -> ExperimentReport:
    """Run a deterministic experiment when H1 is approved; else raise PermissionError."""
    assert_modeling_allowed(state)
    gate = modeling_gate_status(state)

    proposal_model = _as_proposal(proposal)
    if proposal_model is None and state:
        proposal_model = _as_proposal(state.get("research_proposal"))
    if proposal_model is None:
        raise ValueError("Research proposal is required for modeling experiments.")

    candidate_id = _selected_candidate_id(state, proposal_model, selected_candidate_id)
    cfg = settings or get_settings()
    sandbox = _sandbox_enabled(cfg, allow_sandboxed_python)

    run = execute_experiment_run(
        proposal=proposal_model,
        selected_candidate_id=candidate_id,
        problem_specification=problem_specification
        or ((state or {}).get("problem_specification") if state else None),
        h1_decision_id=_h1_decision_id(state),
        strategy_id=strategy_id,
        lookback_days=lookback_days,
        rebalance_every_n_days=rebalance_every_n_days,
        allow_sandboxed_python=sandbox,
    )

    notes = [
        "Phase 6 deterministic fixture runner completed.",
        f"modeling_gate.reason={gate.reason}",
        "Attach results, then run Validation / H2 (Phase 7) separately.",
    ]
    if run.sandboxed_python_note:
        notes.append(run.sandboxed_python_note)

    return ExperimentReport(
        report_id=f"erep_{run.run_id.removeprefix('erun_')}"[:64],
        problem_id=run.constraints.problem_id,
        proposal_id=run.proposal_id,
        selected_candidate_id=run.selected_candidate_id,
        h1_approved=True,
        modeling_allowed=True,
        runs=[run],
        latest_run_id=run.run_id,
        strategy="deterministic_fixture",
        invented_results=False,
        live_trading_api_used=False,
        agent_prompt_version=PROMPT_VERSION,
        analysis_notes=notes,
    )


def latest_run(report: ExperimentReport | dict[str, Any] | None) -> ExperimentRun | None:
    if report is None:
        return None
    model = (
        report
        if isinstance(report, ExperimentReport)
        else ExperimentReport.model_validate(report)
    )
    if not model.runs:
        return None
    if model.latest_run_id:
        for run in model.runs:
            if run.run_id == model.latest_run_id:
                return run
    return model.runs[-1]
