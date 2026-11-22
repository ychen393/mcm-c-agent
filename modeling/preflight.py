"""Read-only Sprint A preflight: verify H1 version and actual implementation mapping.

This never changes a trade strategy, approves a plan or runs a backtest.
Legacy saved plans remain readable. V2 unimplemented strategies are blocked.
"""
from __future__ import annotations

from typing import Any

from tools.research_persistence import as_research_proposal, proposal_sha256


def research_execution_preflight(
    state: dict[str, Any] | None, selected_candidate_id: str | None = None,
    explicit_strategy_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {"allowed": False, "reason": "Project must be initialized"}
    raw = state.get("research_proposal") or {}
    if not isinstance(raw, dict) or not raw:
        return {"allowed": False, "reason": "No saved research plan"}
    proposal = as_research_proposal(raw)
    if proposal.research_decision is None:
        # Legacy behavior remains available to prevent historical-project
        # breakage. Migration to a V2 plan is shown as a warning in the UI.
        return {"allowed": True, "reason": "Legacy plan: strategy mapping not verified", "legacy": True}
    decision = (state.get("decision_report") or {}).get("h1") or {}
    if ((state.get("approval_status") or {}).get("h1") != "approved"
            or decision.get("status") != "approved"):
        return {"allowed": False, "reason": "H1 must be approved on the saved plan"}
    cid = selected_candidate_id or decision.get("selected_candidate_id")
    if cid != decision.get("selected_candidate_id"):
        return {"allowed": False, "reason": "Selected modeling candidate differs from H1 approval"}
    if (decision.get("proposal_id") != proposal.proposal_id
            or decision.get("proposal_sha256") != proposal_sha256(proposal)):
        return {"allowed": False, "reason": "Approved proposal ID/hash does not match latest saved plan"}
    candidate = next((c for c in proposal.candidates if c.candidate_id == cid), None)
    if candidate is None or candidate.execution_plan is None:
        return {"allowed": False, "reason": "Selected method has no executable research specification"}
    plan = candidate.execution_plan
    if plan.implementation_status != "implemented":
        return {"allowed": False, "reason": (
            "This approved research approach still requires implementation or "
            "verification of its trading execution and timing in Sprint B."
        )}
    if (not plan.executable_strategy_id
            or (explicit_strategy_id is not None and
                plan.executable_strategy_id != explicit_strategy_id)):
        return {"allowed": False, "reason": "Runnable strategy ID must exactly match the approved plan"}
    return {"allowed": True, "reason": "Approved strategy and executable implementation match", "legacy": False}
