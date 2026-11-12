"""Sanitize Paper / LaTeX / H3 decisions into ResearchState (Phase 8).

Persisted payloads must pass Phase 1 sanitize_state_for_persistence rules.
Paper attach is refused unless H2 is approved. H3 is never auto-approved;
Phase 9 E2E stays blocked until human H3 approval.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from core.project_store import ProjectStore, make_approval
from paper.gate import (
    assert_paper_allowed,
    e2e_gate_status,
    paper_generation_gate_status,
)
from schemas.paper import H3Decision, PaperPackage
from schemas.persistence import assert_safe_for_persistence
from validation.gate import paper_gate_status

PAPER_PACKAGE_VERSION = "paper_package_1.0"
H3_DECISION_VERSION = "h3_decision_1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def package_sha256(package: PaperPackage | dict[str, Any]) -> str:
    model = (
        package if isinstance(package, PaperPackage) else PaperPackage.model_validate(package)
    )
    payload = model.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compact_paper_package(
    package: PaperPackage | dict[str, Any],
) -> dict[str, Any]:
    """Return a persistence-safe dump of the paper package."""
    model = (
        package if isinstance(package, PaperPackage) else PaperPackage.model_validate(package)
    )
    if model.invented_citations or model.outline.invented_citations:
        raise ValueError("Refusing to persist paper package with invented citations.")
    if not model.h2_approved or not model.paper_allowed:
        raise ValueError("Refusing to persist paper package without H2-approved gate.")
    if any(entry.invented for entry in model.outline.bib_entries):
        raise ValueError("Refusing to persist invented bibliography entries.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = PAPER_PACKAGE_VERSION
    payload["invented_citations"] = False
    assert_safe_for_persistence(payload, "paper_package")
    return payload


def compact_h3_decision(decision: H3Decision | dict[str, Any]) -> dict[str, Any]:
    model = decision if isinstance(decision, H3Decision) else H3Decision.model_validate(decision)
    if model.auto_approved:
        raise ValueError("Refusing to persist auto-approved H3 decision.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = H3_DECISION_VERSION
    payload["auto_approved"] = False
    assert_safe_for_persistence(payload, "decision_report.h3")
    return payload


def persist_paper_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    package: PaperPackage | dict[str, Any],
    note: str = "phase8-paper-latex",
) -> dict[str, Any]:
    """Attach sanitized paper outline / latex / review. Requires H2 approved."""
    assert_paper_allowed(state)
    compact = compact_paper_package(package)
    outline = compact.get("outline") or {}
    latex = compact.get("latex") or {}
    review = compact.get("review") or {}

    updated = dict(state)
    updated["paper_outline"] = {
        **outline,
        "package_id": compact.get("package_id"),
        "report_version": PAPER_PACKAGE_VERSION,
    }
    updated["latex_source"] = str(latex.get("tex_source") or "")
    # Keep bib alongside review metadata under review_report for Phase 1 fields.
    updated["review_report"] = {
        **review,
        "bib_source": latex.get("bib_source") or "",
        "latex_bundle_id": latex.get("bundle_id"),
        "package_id": compact.get("package_id"),
        "compile_attempted": latex.get("compile_attempted"),
        "compile_ok": latex.get("compile_ok"),
        "compile_note": latex.get("compile_note"),
    }

    # Reset H3 when a new paper package is attached — never inherit silent approval.
    approval_status = dict(updated.get("approval_status") or {})
    approval_status["h3"] = "pending"
    updated["approval_status"] = approval_status

    decision_report = dict(updated.get("decision_report") or {})
    decision_report["paper"] = compact
    decision_report["h3"] = {
        "status": "pending",
        "auto_approved": False,
        "decided_by": None,
        "notes": "Awaiting explicit human H3 Approve / Request-revision.",
        "package_id": compact.get("package_id"),
        "outline_id": outline.get("outline_id"),
    }
    decision_report["paper_gate"] = paper_gate_status(updated).model_dump(mode="json")
    decision_report["paper_generation_gate"] = paper_generation_gate_status(updated).model_dump(
        mode="json"
    )
    decision_report["e2e_gate"] = e2e_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision_report

    phases = dict(updated.get("workspace_phases") or {})
    phases["paper_latex"] = "recorded"
    phases["h3"] = "pending"
    phases["e2e_acceptance"] = "blocked_until_h3"
    updated["workspace_phases"] = phases

    # Do not mark research_task_complete or start Phase 9.
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


def build_h3_decision(
    *,
    status: Literal["approved", "revision_requested", "rejected"],
    package: PaperPackage | dict[str, Any],
    notes: str = "",
) -> H3Decision:
    """Construct a human H3 decision. Never sets auto_approved."""
    model = (
        package if isinstance(package, PaperPackage) else PaperPackage.model_validate(package)
    )
    digest = hashlib.sha256(
        f"{model.package_id}|{status}|{notes}".encode("utf-8")
    ).hexdigest()[:10]
    return H3Decision(
        decision_id=f"h3d_{digest}",
        status=status,
        package_id=model.package_id,
        outline_id=model.outline.outline_id,
        notes=notes,
        decided_by="human",
        auto_approved=False,
        decided_at_utc=_utc_now(),
        package_sha256=package_sha256(model),
    )


def persist_h3_decision_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    decision: H3Decision | dict[str, Any],
    note: str = "phase8-h3-decision",
) -> dict[str, Any]:
    """Persist human H3 decision. Refuses auto-approval. Does not start Phase 9."""
    h3 = decision if isinstance(decision, H3Decision) else H3Decision.model_validate(decision)
    if h3.auto_approved:
        raise ValueError("H3 auto-approval is forbidden.")
    compact = compact_h3_decision(h3)
    updated = dict(state)
    approval_status = dict(updated.get("approval_status") or {})
    approval_status["h3"] = h3.status
    updated["approval_status"] = approval_status

    decision_report = dict(updated.get("decision_report") or {})
    decision_report["h3"] = compact
    updated["decision_report"] = decision_report
    decision_report["paper_gate"] = paper_gate_status(updated).model_dump(mode="json")
    decision_report["paper_generation_gate"] = paper_generation_gate_status(updated).model_dump(
        mode="json"
    )
    decision_report["e2e_gate"] = e2e_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision_report

    phases = dict(updated.get("workspace_phases") or {})
    phases["h3"] = h3.status
    if h3.status == "approved":
        phases["paper_latex"] = "h3_approved"
        # Phase 9 is not started — keep explicit blocked-until-implemented label.
        phases["e2e_acceptance"] = "h3_approved_phase9_pending"
    elif h3.status == "revision_requested":
        phases["paper_latex"] = "revision_requested"
        phases["e2e_acceptance"] = "blocked_until_h3"
    else:
        phases["paper_latex"] = "h3_rejected"
        phases["e2e_acceptance"] = "blocked_until_h3"
    updated["workspace_phases"] = phases

    # Never mark research_task_complete in Phase 8; never auto-start Phase 9.
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
                gate="H3",
                status=(
                    "approved"
                    if h3.status == "approved"
                    else ("rejected" if h3.status == "rejected" else "pending")
                ),
                notes=h3.notes or f"H3 {h3.status}",
                subject_sha256=h3.package_sha256,
            )
        )
    except Exception:
        pass

    saved = dict(saved)
    saved["run_id"] = run_id
    saved["data_resume"] = "reupload_required"
    return saved
