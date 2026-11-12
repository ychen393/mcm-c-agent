"""Validation readiness + Paper gates (Phase 7).

Validation / sensitivity runs only when human H1 is approved **and** Phase 6
experiment results are available on ResearchState. Paper Planner / LaTeX
(Phase 8) stays blocked until human H2 is approved. This module never
auto-approves H1 or H2 and never starts paper generation.
"""

from __future__ import annotations

from typing import Any

from modeling.gate import read_h1_status
from schemas.validation import (
    H2DecisionStatus,
    PaperGateStatus,
    ValidationGateStatus,
)

_H1_BLOCKED = {
    "absent": ("h1_absent", "H1 decision absent — Validation / H2 remain blocked."),
    "pending": (
        "h1_pending",
        "H1 is pending human Approve / Request-revision — validation blocked.",
    ),
    "revision_requested": (
        "h1_revision_requested",
        "H1 requested revision — revise the proposal before validation.",
    ),
    "rejected": (
        "h1_rejected",
        "H1 rejected the research plan — validation blocked.",
    ),
}

_H2_BLOCKED = {
    "absent": "H2 decision absent — Paper Planner / LaTeX remain blocked.",
    "pending": "H2 is pending human Approve / Request-revision — paper blocked.",
    "revision_requested": "H2 requested revision — revise validation before paper.",
    "rejected": "H2 rejected validation — Paper Planner / LaTeX blocked.",
}


def _experiment_payload(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the Phase 6 experiment report dict if present on state."""
    if not state:
        return None
    decision = state.get("decision_report") or {}
    if isinstance(decision, dict):
        experiment = decision.get("experiment")
        if isinstance(experiment, dict) and experiment.get("report_id"):
            return experiment
    logs = state.get("experiment_logs") or []
    if isinstance(logs, list) and logs:
        # Prefer a completed log with run_id as a minimal availability signal.
        for entry in reversed(logs):
            if isinstance(entry, dict) and entry.get("run_id") and entry.get("status") == "completed":
                return {
                    "report_id": None,
                    "latest_run_id": entry.get("run_id"),
                    "runs": [entry],
                    "from_experiment_logs": True,
                }
    return None


def resolve_baseline_run_id(state: dict[str, Any] | None) -> str | None:
    """Pick the baseline Phase 6 run id from experiment report or logs."""
    payload = _experiment_payload(state)
    if not payload:
        return None
    latest = payload.get("latest_run_id")
    if isinstance(latest, str) and latest:
        return latest
    runs = payload.get("runs") or []
    if isinstance(runs, list) and runs:
        last = runs[-1]
        if isinstance(last, dict) and last.get("run_id"):
            return str(last["run_id"])
    if payload.get("run_id"):
        return str(payload["run_id"])
    return None


def has_experiment_results(state: dict[str, Any] | None) -> bool:
    """True when a usable Phase 6 experiment result is attached."""
    payload = _experiment_payload(state)
    if not payload:
        return False
    runs = payload.get("runs") or []
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            if run.get("status") == "completed" and (
                run.get("metrics") or run.get("run_id")
            ):
                return True
    return bool(resolve_baseline_run_id(state))


def validation_allowed(state: dict[str, Any] | None) -> bool:
    """True only when H1 approved and experiment results exist. Never auto-true."""
    return validation_gate_status(state).validation_allowed


def validation_gate_status(state: dict[str, Any] | None) -> ValidationGateStatus:
    """Structured validation gate for UI / persistence. Default is blocked."""
    h1 = read_h1_status(state)
    experiments_ok = has_experiment_results(state)
    baseline = resolve_baseline_run_id(state)

    if h1 != "approved":
        key = h1 if h1 in _H1_BLOCKED else "absent"
        reason, message = _H1_BLOCKED[key]
        return ValidationGateStatus(
            validation_allowed=False,
            h1_status=h1 or "absent",
            has_experiment_results=experiments_ok,
            baseline_run_id=baseline,
            reason=reason,  # type: ignore[arg-type]
            message=message,
        )

    if not experiments_ok:
        return ValidationGateStatus(
            validation_allowed=False,
            h1_status="approved",
            has_experiment_results=False,
            baseline_run_id=None,
            reason="no_experiment_results",
            message=(
                "H1 is approved but no Phase 6 experiment results are available. "
                "Run and attach Modeling & Experiment before Validation / H2."
            ),
        )

    if not baseline:
        return ValidationGateStatus(
            validation_allowed=False,
            h1_status="approved",
            has_experiment_results=True,
            baseline_run_id=None,
            reason="experiment_incomplete",
            message=(
                "Experiment results are present but incomplete (missing baseline "
                "run id / metrics). Re-run Phase 6 attach before validation."
            ),
        )

    return ValidationGateStatus(
        validation_allowed=True,
        h1_status="approved",
        has_experiment_results=True,
        baseline_run_id=baseline,
        reason="validation_allowed",
        message=(
            "H1 approved and Phase 6 experiment results available. Validation / "
            "sensitivity (Phase 7) may run the deterministic fixture path. H1 and "
            "H2 are never auto-approved; Paper / LaTeX remains Phase 8."
        ),
    )


def assert_validation_allowed(state: dict[str, Any] | None) -> None:
    """Raise if callers attempt validation without H1 + experiment results."""
    gate = validation_gate_status(state)
    if not gate.validation_allowed:
        raise PermissionError(gate.message)


def read_h2_status(state: dict[str, Any] | None) -> H2DecisionStatus | None:
    """Read H2 status from ResearchState-like mapping. None if absent."""
    if not state:
        return None
    approval = state.get("approval_status") or {}
    if isinstance(approval, dict):
        raw = approval.get("h2") or approval.get("H2")
        if raw in {"pending", "approved", "revision_requested", "rejected"}:
            return raw  # type: ignore[return-value]
    decision_report = state.get("decision_report") or {}
    if isinstance(decision_report, dict):
        h2 = decision_report.get("h2") or {}
        if isinstance(h2, dict):
            raw = h2.get("status")
            if raw in {"pending", "approved", "revision_requested", "rejected"}:
                return raw  # type: ignore[return-value]
    return None


def paper_allowed(state: dict[str, Any] | None) -> bool:
    """True only when human H2 status is approved. Never auto-true."""
    return read_h2_status(state) == "approved"


def paper_gate_status(state: dict[str, Any] | None) -> PaperGateStatus:
    """Structured paper gate. Default is blocked until human H2 approval."""
    validation = (state or {}).get("validation_report") if state else None
    has_validation = isinstance(validation, dict) and bool(validation.get("report_id"))
    status = read_h2_status(state)

    if status == "approved":
        return PaperGateStatus(
            paper_allowed=True,
            h2_status="approved",
            reason="h2_approved",
            message=(
                "H2 approved by a human. Paper Planner / LaTeX (Phase 8) may "
                "advance. H2 is never auto-approved."
            ),
        )
    if status == "pending":
        return PaperGateStatus(
            paper_allowed=False,
            h2_status="pending",
            reason="h2_pending",
            message=_H2_BLOCKED["pending"],
        )
    if status == "revision_requested":
        return PaperGateStatus(
            paper_allowed=False,
            h2_status="revision_requested",
            reason="h2_revision_requested",
            message=_H2_BLOCKED["revision_requested"],
        )
    if status == "rejected":
        return PaperGateStatus(
            paper_allowed=False,
            h2_status="rejected",
            reason="h2_rejected",
            message=_H2_BLOCKED["rejected"],
        )
    if not has_validation:
        return PaperGateStatus(
            paper_allowed=False,
            h2_status="absent",
            reason="no_validation_report",
            message=(
                "No validation report attached — run Validation / sensitivity "
                "and obtain human H2 before Paper / LaTeX."
            ),
        )
    return PaperGateStatus(
        paper_allowed=False,
        h2_status="absent",
        reason="h2_not_decided",
        message=_H2_BLOCKED["absent"],
    )


def assert_paper_allowed(state: dict[str, Any] | None) -> None:
    """Raise if callers attempt Paper / LaTeX without human H2 approval."""
    gate = paper_gate_status(state)
    if not gate.paper_allowed:
        raise PermissionError(gate.message)
