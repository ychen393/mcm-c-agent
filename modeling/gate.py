"""Modeling readiness gate (Phase 5).

Mathematical Modeling & Experiment (Phase 6) must stay blocked until a human
approves H1. This module never auto-approves and never starts modeling.
"""

from __future__ import annotations

from typing import Any

from schemas.research import H1DecisionStatus, ModelingGateStatus

_BLOCKED_MESSAGES = {
    "absent": "H1 decision absent — Modeling & Experiment remain blocked.",
    "pending": "H1 is pending human Approve / Request-revision — modeling blocked.",
    "revision_requested": "H1 requested revision — revise the proposal before modeling.",
    "rejected": "H1 rejected the research plan — modeling blocked.",
}


def read_h1_status(state: dict[str, Any] | None) -> H1DecisionStatus | None:
    """Read H1 status from ResearchState-like mapping. None if absent."""
    if not state:
        return None
    approval = state.get("approval_status") or {}
    if isinstance(approval, dict):
        raw = approval.get("h1") or approval.get("H1")
        if raw in {"pending", "approved", "revision_requested", "rejected"}:
            return raw  # type: ignore[return-value]
    decision_report = state.get("decision_report") or {}
    if isinstance(decision_report, dict):
        h1 = decision_report.get("h1") or {}
        if isinstance(h1, dict):
            raw = h1.get("status")
            if raw in {"pending", "approved", "revision_requested", "rejected"}:
                return raw  # type: ignore[return-value]
    return None


def modeling_allowed(state: dict[str, Any] | None) -> bool:
    """True only when human H1 status is approved. Never auto-true."""
    return read_h1_status(state) == "approved"


def modeling_gate_status(state: dict[str, Any] | None) -> ModelingGateStatus:
    """Structured gate for UI / persistence. Default is blocked."""
    proposal = (state or {}).get("research_proposal") if state else None
    has_proposal = isinstance(proposal, dict) and bool(proposal)
    status = read_h1_status(state)

    if status == "approved":
        return ModelingGateStatus(
            modeling_allowed=True,
            h1_status="approved",
            reason="h1_approved",
            message=(
                "H1 approved by a human. Modeling & Experiment (Phase 6) may proceed "
                "when that phase is implemented — Phase 5 does not start modeling."
            ),
        )
    if status == "pending":
        return ModelingGateStatus(
            modeling_allowed=False,
            h1_status="pending",
            reason="h1_pending",
            message=_BLOCKED_MESSAGES["pending"],
        )
    if status == "revision_requested":
        return ModelingGateStatus(
            modeling_allowed=False,
            h1_status="revision_requested",
            reason="h1_revision_requested",
            message=_BLOCKED_MESSAGES["revision_requested"],
        )
    if status == "rejected":
        return ModelingGateStatus(
            modeling_allowed=False,
            h1_status="rejected",
            reason="h1_rejected",
            message=_BLOCKED_MESSAGES["rejected"],
        )
    if not has_proposal:
        return ModelingGateStatus(
            modeling_allowed=False,
            h1_status="absent",
            reason="no_proposal",
            message="No research proposal attached — synthesize candidates before H1.",
        )
    return ModelingGateStatus(
        modeling_allowed=False,
        h1_status="absent",
        reason="h1_not_decided",
        message=_BLOCKED_MESSAGES["absent"],
    )


def assert_modeling_allowed(state: dict[str, Any] | None) -> None:
    """Raise if callers attempt modeling without human H1 approval."""
    gate = modeling_gate_status(state)
    if not gate.modeling_allowed:
        raise PermissionError(gate.message)
