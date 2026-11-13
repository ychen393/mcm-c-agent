"""Sanitize Validation / Sensitivity / H2 decisions into ResearchState (Phase 7).

Persisted payloads must pass Phase 1 sanitize_state_for_persistence rules.
Validation attach is refused unless H1 is approved and experiment results exist.
H2 is never auto-approved; Paper / LaTeX stays blocked until human H2 approval.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from core.project_store import ProjectStore, make_approval
from schemas.persistence import assert_safe_for_persistence
from schemas.validation import H2Decision, ValidationReport
from validation.gate import (
    assert_validation_allowed,
    paper_gate_status,
    validation_gate_status,
)

VALIDATION_REPORT_VERSION = "validation_report_1.0"
H2_DECISION_VERSION = "h2_decision_1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_validation_report(report: ValidationReport | dict[str, Any]) -> ValidationReport:
    if isinstance(report, ValidationReport):
        return report
    from tools.research_persistence import strip_persistence_only

    return ValidationReport.model_validate(strip_persistence_only(report))


def validation_sha256(report: ValidationReport | dict[str, Any]) -> str:
    model = as_validation_report(report)
    payload = model.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compact_validation_report(
    report: ValidationReport | dict[str, Any],
) -> dict[str, Any]:
    """Return a persistence-safe dump of the validation report."""
    model = as_validation_report(report)
    if model.invented_results or model.live_trading_api_used:
        raise ValueError("Refusing to persist unsafe validation report.")
    if not model.h1_approved or not model.validation_allowed:
        raise ValueError(
            "Refusing to persist validation report without H1-approved gate."
        )
    if any(s.invented_results for s in model.scenarios):
        raise ValueError("Refusing to persist invented scenario results.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = VALIDATION_REPORT_VERSION
    payload["invented_results"] = False
    payload["live_trading_api_used"] = False
    assert_safe_for_persistence(payload, "validation_report")
    return payload


def compact_h2_decision(decision: H2Decision | dict[str, Any]) -> dict[str, Any]:
    model = decision if isinstance(decision, H2Decision) else H2Decision.model_validate(decision)
    if model.auto_approved:
        raise ValueError("Refusing to persist auto-approved H2 decision.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = H2_DECISION_VERSION
    payload["auto_approved"] = False
    assert_safe_for_persistence(payload, "decision_report.h2")
    return payload


def persist_validation_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    report: ValidationReport | dict[str, Any],
    note: str = "phase7-validation-sensitivity",
) -> dict[str, Any]:
    """Attach sanitized validation report. Requires H1 + experiment results."""
    assert_validation_allowed(state)
    compact = compact_validation_report(report)
    updated = dict(state)
    updated["validation_report"] = compact

    # Reset H2 when a new validation report is attached — never inherit silent approval.
    approval_status = dict(updated.get("approval_status") or {})
    approval_status["h2"] = "pending"
    updated["approval_status"] = approval_status

    decision_report = dict(updated.get("decision_report") or {})
    decision_report["validation"] = compact
    decision_report["h2"] = {
        "status": "pending",
        "auto_approved": False,
        "decided_by": None,
        "notes": "Awaiting explicit human H2 Approve / Request-revision.",
        "validation_report_id": compact.get("report_id"),
        "baseline_run_id": compact.get("baseline_run_id"),
    }
    decision_report["validation_gate"] = validation_gate_status(updated).model_dump(
        mode="json"
    )
    decision_report["paper_gate"] = paper_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision_report

    phases = dict(updated.get("workspace_phases") or {})
    phases["validation_sensitivity"] = "recorded"
    phases["h2"] = "pending"
    phases["paper_latex"] = "blocked_until_h2"
    updated["workspace_phases"] = phases

    # Do not mark research_task_complete or start Phase 8 paper / LaTeX.
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


def build_h2_decision(
    *,
    status: Literal["approved", "revision_requested", "rejected"],
    report: ValidationReport | dict[str, Any],
    notes: str = "",
) -> H2Decision:
    """Construct a human H2 decision. Never sets auto_approved."""
    model = as_validation_report(report)
    digest = hashlib.sha256(
        f"{model.report_id}|{status}|{notes}".encode("utf-8")
    ).hexdigest()[:10]
    return H2Decision(
        decision_id=f"h2d_{digest}",
        status=status,
        validation_report_id=model.report_id,
        baseline_run_id=model.baseline_run_id,
        proposal_id=model.proposal_id,
        notes=notes,
        decided_by="human",
        auto_approved=False,
        decided_at_utc=_utc_now(),
        validation_sha256=validation_sha256(model),
    )


def persist_h2_decision_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    decision: H2Decision | dict[str, Any],
    note: str = "phase7-h2-decision",
) -> dict[str, Any]:
    """Persist human H2 decision. Refuses auto-approval. Does not start Phase 8."""
    h2 = decision if isinstance(decision, H2Decision) else H2Decision.model_validate(decision)
    if h2.auto_approved:
        raise ValueError("H2 auto-approval is forbidden.")
    compact = compact_h2_decision(h2)
    updated = dict(state)
    approval_status = dict(updated.get("approval_status") or {})
    approval_status["h2"] = h2.status
    updated["approval_status"] = approval_status

    decision_report = dict(updated.get("decision_report") or {})
    decision_report["h2"] = compact
    updated["decision_report"] = decision_report
    # Refresh gates after writing approval_status.
    decision_report["validation_gate"] = validation_gate_status(updated).model_dump(
        mode="json"
    )
    decision_report["paper_gate"] = paper_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision_report

    phases = dict(updated.get("workspace_phases") or {})
    phases["h2"] = h2.status
    if h2.status == "approved":
        phases["validation_sensitivity"] = "h2_approved"
        # Paper agent is still Phase 8 — keep explicit blocked-until-implemented label.
        phases["paper_latex"] = "h2_approved_phase8_pending"
    elif h2.status == "revision_requested":
        phases["validation_sensitivity"] = "revision_requested"
        phases["paper_latex"] = "blocked_until_h2"
    else:
        phases["validation_sensitivity"] = "h2_rejected"
        phases["paper_latex"] = "blocked_until_h2"
    updated["workspace_phases"] = phases

    # Never mark research_task_complete in Phase 7; never auto-start Phase 8.
    assert_safe_for_persistence(updated, "state")

    _project, run, saved = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=updated,
        input_signature=input_signature,
        note=note,
    )
    run_id = run.run_id
    try:
        store.add_approval(
            make_approval(
                project_id=project_id,
                run_id=run_id,
                gate="H2",
                status=(
                    "approved"
                    if h2.status == "approved"
                    else ("rejected" if h2.status == "rejected" else "pending")
                ),
                notes=h2.notes or f"H2 {h2.status}",
                subject_sha256=h2.validation_sha256,
            )
        )
    except Exception:
        pass

    saved = dict(saved)
    saved["run_id"] = run_id
    saved["data_resume"] = "reupload_required"
    return saved
