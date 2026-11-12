"""Paper generation + Phase 9 E2E gates (Phase 8).

Paper Planner / LaTeX runs only when human H2 is approved (delegates to
``validation.gate``). Phase 9 E2E acceptance stays blocked until human H3 is
approved. This module never auto-approves H1, H2, or H3 and never starts Phase 9.
"""

from __future__ import annotations

from typing import Any

from schemas.paper import E2EGateStatus, H3DecisionStatus, PaperGenerationGateStatus
from validation.gate import (
    assert_paper_allowed,
    paper_allowed,
    paper_gate_status,
    read_h2_status,
)

_H3_BLOCKED = {
    "absent": "H3 decision absent — Phase 9 E2E acceptance remains blocked.",
    "pending": "H3 is pending human Approve / Request-revision — E2E blocked.",
    "revision_requested": "H3 requested revision — revise the paper before E2E.",
    "rejected": "H3 rejected the paper package — Phase 9 E2E blocked.",
}


def paper_generation_gate_status(
    state: dict[str, Any] | None,
) -> PaperGenerationGateStatus:
    """Structured paper-generation gate wrapping Phase 7 paper_gate_status."""
    base = paper_gate_status(state)
    return PaperGenerationGateStatus(
        paper_allowed=base.paper_allowed,
        h2_status=base.h2_status if base.h2_status != "absent" else "absent",
        reason=base.reason,  # type: ignore[arg-type]
        message=base.message,
    )


def read_h3_status(state: dict[str, Any] | None) -> H3DecisionStatus | None:
    """Read H3 status from ResearchState-like mapping. None if absent."""
    if not state:
        return None
    approval = state.get("approval_status") or {}
    if isinstance(approval, dict):
        raw = approval.get("h3") or approval.get("H3")
        if raw in {"pending", "approved", "revision_requested", "rejected"}:
            return raw  # type: ignore[return-value]
    decision_report = state.get("decision_report") or {}
    if isinstance(decision_report, dict):
        h3 = decision_report.get("h3") or {}
        if isinstance(h3, dict):
            raw = h3.get("status")
            if raw in {"pending", "approved", "revision_requested", "rejected"}:
                return raw  # type: ignore[return-value]
    return None


def e2e_allowed(state: dict[str, Any] | None) -> bool:
    """True only when human H3 status is approved. Never auto-true."""
    return read_h3_status(state) == "approved"


def e2e_gate_status(state: dict[str, Any] | None) -> E2EGateStatus:
    """Structured Phase 9 gate. Default blocked until human H3 approval."""
    outline = (state or {}).get("paper_outline") if state else None
    has_outline = isinstance(outline, dict) and bool(
        outline.get("outline_id") or outline.get("package_id")
    )
    status = read_h3_status(state)

    if status == "approved":
        return E2EGateStatus(
            e2e_allowed=True,
            h3_status="approved",
            reason="h3_approved",
            message=(
                "H3 approved by a human. Phase 9 E2E acceptance may advance. "
                "H3 is never auto-approved."
            ),
        )
    if status == "pending":
        return E2EGateStatus(
            e2e_allowed=False,
            h3_status="pending",
            reason="h3_pending",
            message=_H3_BLOCKED["pending"],
        )
    if status == "revision_requested":
        return E2EGateStatus(
            e2e_allowed=False,
            h3_status="revision_requested",
            reason="h3_revision_requested",
            message=_H3_BLOCKED["revision_requested"],
        )
    if status == "rejected":
        return E2EGateStatus(
            e2e_allowed=False,
            h3_status="rejected",
            reason="h3_rejected",
            message=_H3_BLOCKED["rejected"],
        )
    if not has_outline:
        return E2EGateStatus(
            e2e_allowed=False,
            h3_status="absent",
            reason="no_paper_outline",
            message=(
                "No paper outline attached — run Paper Planner / LaTeX and "
                "obtain human H3 before Phase 9 E2E."
            ),
        )
    return E2EGateStatus(
        e2e_allowed=False,
        h3_status="absent",
        reason="h3_not_decided",
        message=_H3_BLOCKED["absent"],
    )


def assert_e2e_allowed(state: dict[str, Any] | None) -> None:
    """Raise if callers attempt Phase 9 E2E without human H3 approval."""
    gate = e2e_gate_status(state)
    if not gate.e2e_allowed:
        raise PermissionError(gate.message)


__all__ = [
    "assert_e2e_allowed",
    "assert_paper_allowed",
    "e2e_allowed",
    "e2e_gate_status",
    "paper_allowed",
    "paper_generation_gate_status",
    "paper_gate_status",
    "read_h2_status",
    "read_h3_status",
]
