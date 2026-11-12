"""Human-gate test doubles for the Phase 9 E2E harness.

IMPORTANT
---------
These helpers exist **only** so the offline acceptance harness can advance past
H1 / H2 / H3 without a live Streamlit clicker. They:

* call the same ``build_h*_decision`` / ``persist_h*_decision_into_state``
  paths used by the product UI;
* always set ``decided_by="human"`` and ``auto_approved=False``;
* stamp explicit harness provenance (``harness_simulated_human=True``);
* **never** enable production auto-approve.

Product UI panels (``app/research_h1_panel.py``, ``app/validation_h2_panel.py``,
``app/paper_h3_panel.py``) remain the only human path in the running app.
"""

from __future__ import annotations

from typing import Any, Literal

from core.project_store import ProjectStore
from schemas.e2e import HarnessGateRecord
from schemas.paper import PaperPackage
from schemas.research import ResearchProposal
from schemas.validation import ValidationReport
from tools.paper_persistence import build_h3_decision, persist_h3_decision_into_state
from tools.research_persistence import build_h1_decision, persist_h1_decision_into_state
from tools.validation_persistence import build_h2_decision, persist_h2_decision_into_state

from e2e.acceptance_facts import HARNESS_SIMULATED_HUMAN_NOTE

GATE_PRODUCT_VS_HARNESS: dict[str, str] = {
    "H1": (
        "Product: Streamlit Research/H1 panel explicit Approve / Request-revision. "
        "Harness: apply_harness_h1_approval test double (simulated human; never auto)."
    ),
    "H2": (
        "Product: Streamlit Validation/H2 panel explicit Approve / Request-revision. "
        "Harness: apply_harness_h2_approval test double (simulated human; never auto)."
    ),
    "H3": (
        "Product: Streamlit Paper/H3 panel explicit Approve / Request-revision. "
        "Harness: apply_harness_h3_approval test double (simulated human; never auto)."
    ),
}


def _record_gate(
    state: dict[str, Any],
    record: HarnessGateRecord,
) -> dict[str, Any]:
    """Attach harness gate provenance under decision_report.e2e_harness."""
    updated = dict(state)
    decision = dict(updated.get("decision_report") or {})
    harness = dict(decision.get("e2e_harness") or {})
    gates = list(harness.get("gates") or [])
    gates.append(record.model_dump(mode="json"))
    harness["gates"] = gates
    harness["product_ui_gates_remain_human_only"] = True
    harness["never_auto_approve"] = ["H1", "H2", "H3"]
    harness["representation"] = "harness_test_double"
    decision["e2e_harness"] = harness
    updated["decision_report"] = decision
    return updated


def apply_harness_h1_approval(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    proposal: ResearchProposal | dict[str, Any],
    selected_candidate_id: str | None = None,
    critique_id: str | None = None,
    notes: str | None = None,
) -> tuple[dict[str, Any], HarnessGateRecord]:
    """Simulate a human H1 Approve inside the E2E harness only."""
    decision = build_h1_decision(
        status="approved",
        proposal=proposal,
        selected_candidate_id=selected_candidate_id,
        notes=notes or HARNESS_SIMULATED_HUMAN_NOTE,
        critique_id=critique_id,
    )
    if decision.auto_approved:
        raise RuntimeError("H1 harness double refused: auto_approved must be False")
    if decision.decided_by != "human":
        raise RuntimeError("H1 harness double refused: decided_by must be human")
    saved = persist_h1_decision_into_state(
        store,
        project_id=project_id,
        project_name=project_name,
        state=state,
        input_signature=input_signature,
        decision=decision,
        note="phase9-e2e-harness-h1-simulated-human",
    )
    record = HarnessGateRecord(
        gate="H1",
        status="approved",
        notes=decision.notes or HARNESS_SIMULATED_HUMAN_NOTE,
        decision_id=decision.decision_id,
    )
    saved = _record_gate(saved, record)
    # Re-save provenance so it survives subsequent reads from store callers.
    _project, run, saved2 = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=saved,
        input_signature=input_signature,
        note="phase9-e2e-harness-h1-provenance",
    )
    saved2 = dict(saved2)
    saved2["run_id"] = run.run_id
    return saved2, record


def apply_harness_h2_approval(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    report: ValidationReport | dict[str, Any],
    notes: str | None = None,
) -> tuple[dict[str, Any], HarnessGateRecord]:
    """Simulate a human H2 Approve inside the E2E harness only."""
    decision = build_h2_decision(
        status="approved",
        report=report,
        notes=notes or HARNESS_SIMULATED_HUMAN_NOTE,
    )
    if decision.auto_approved:
        raise RuntimeError("H2 harness double refused: auto_approved must be False")
    if decision.decided_by != "human":
        raise RuntimeError("H2 harness double refused: decided_by must be human")
    saved = persist_h2_decision_into_state(
        store,
        project_id=project_id,
        project_name=project_name,
        state=state,
        input_signature=input_signature,
        decision=decision,
        note="phase9-e2e-harness-h2-simulated-human",
    )
    record = HarnessGateRecord(
        gate="H2",
        status="approved",
        notes=decision.notes or HARNESS_SIMULATED_HUMAN_NOTE,
        decision_id=decision.decision_id,
    )
    saved = _record_gate(saved, record)
    _project, run, saved2 = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=saved,
        input_signature=input_signature,
        note="phase9-e2e-harness-h2-provenance",
    )
    saved2 = dict(saved2)
    saved2["run_id"] = run.run_id
    return saved2, record


def apply_harness_h3_approval(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    package: PaperPackage | dict[str, Any],
    notes: str | None = None,
) -> tuple[dict[str, Any], HarnessGateRecord]:
    """Simulate a human H3 Approve inside the E2E harness only."""
    decision = build_h3_decision(
        status="approved",
        package=package,
        notes=notes or HARNESS_SIMULATED_HUMAN_NOTE,
    )
    if decision.auto_approved:
        raise RuntimeError("H3 harness double refused: auto_approved must be False")
    if decision.decided_by != "human":
        raise RuntimeError("H3 harness double refused: decided_by must be human")
    saved = persist_h3_decision_into_state(
        store,
        project_id=project_id,
        project_name=project_name,
        state=state,
        input_signature=input_signature,
        decision=decision,
        note="phase9-e2e-harness-h3-simulated-human",
    )
    record = HarnessGateRecord(
        gate="H3",
        status="approved",
        notes=decision.notes or HARNESS_SIMULATED_HUMAN_NOTE,
        decision_id=decision.decision_id,
    )
    saved = _record_gate(saved, record)
    _project, run, saved2 = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=saved,
        input_signature=input_signature,
        note="phase9-e2e-harness-h3-provenance",
    )
    saved2 = dict(saved2)
    saved2["run_id"] = run.run_id
    return saved2, record


def refuse_auto_approved_payload(
    gate: Literal["H1", "H2", "H3"],
    *,
    auto_approved: bool,
) -> None:
    """Shared guard used by tests — harness never accepts auto-approve."""
    if auto_approved:
        raise ValueError(
            f"{gate} harness / product path rejects auto_approved=True "
            "(human gates are never auto-approved)."
        )
