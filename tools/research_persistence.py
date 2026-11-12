"""Sanitize Research Proposal / Critique / H1 decisions into ResearchState (Phase 5).

Persisted payloads must pass Phase 1 sanitize_state_for_persistence rules.
H1 is never auto-approved; modeling stays blocked until human approval.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from core.project_store import ProjectStore, make_approval
from modeling.gate import modeling_gate_status
from schemas.persistence import assert_safe_for_persistence
from schemas.research import DebateCritique, H1Decision, ResearchProposal

PROPOSAL_REPORT_VERSION = "research_proposal_1.0"
DECISION_REPORT_VERSION = "h1_decision_1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def proposal_sha256(proposal: ResearchProposal | dict[str, Any]) -> str:
    model = (
        proposal
        if isinstance(proposal, ResearchProposal)
        else ResearchProposal.model_validate(proposal)
    )
    payload = model.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compact_research_proposal(
    proposal: ResearchProposal | dict[str, Any],
) -> dict[str, Any]:
    """Return a persistence-safe dump of the research proposal."""
    model = (
        proposal
        if isinstance(proposal, ResearchProposal)
        else ResearchProposal.model_validate(proposal)
    )
    if model.invented_sources or any(c.invented_sources for c in model.candidates):
        raise ValueError("Refusing to persist invented research sources.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = PROPOSAL_REPORT_VERSION
    payload["invented_sources"] = False
    assert_safe_for_persistence(payload, "research_proposal")
    return payload


def compact_debate_critique(
    critique: DebateCritique | dict[str, Any],
) -> dict[str, Any]:
    """Return a persistence-safe dump of the debate critique."""
    model = (
        critique
        if isinstance(critique, DebateCritique)
        else DebateCritique.model_validate(critique)
    )
    if model.invented_sources or any(f.invented_source for f in model.findings):
        raise ValueError("Refusing to persist invented critique sources.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = "debate_critique_1.0"
    payload["invented_sources"] = False
    assert_safe_for_persistence(payload, "decision_report.critique")
    return payload


def disagreement_log_from_critique(
    critique: DebateCritique | dict[str, Any],
) -> list[dict[str, Any]]:
    """Compact disagreement_log entries from critique findings."""
    model = (
        critique
        if isinstance(critique, DebateCritique)
        else DebateCritique.model_validate(critique)
    )
    entries: list[dict[str, Any]] = []
    for finding in model.findings:
        entry = {
            "finding_id": finding.finding_id,
            "kind": finding.kind,
            "severity": finding.severity,
            "candidate_id": finding.candidate_id,
            "statement": finding.statement,
            "suggested_action": finding.suggested_action,
            "invented_source": False,
        }
        assert_safe_for_persistence(entry, "disagreement_log")
        entries.append(entry)
    return entries


def compact_h1_decision(decision: H1Decision | dict[str, Any]) -> dict[str, Any]:
    model = decision if isinstance(decision, H1Decision) else H1Decision.model_validate(decision)
    if model.auto_approved:
        raise ValueError("Refusing to persist auto-approved H1 decision.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = DECISION_REPORT_VERSION
    payload["auto_approved"] = False
    assert_safe_for_persistence(payload, "decision_report.h1")
    return payload


def persist_research_proposal_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    proposal: ResearchProposal | dict[str, Any],
    critique: DebateCritique | dict[str, Any] | None = None,
    note: str = "phase5-research-proposal",
) -> dict[str, Any]:
    """Attach sanitized research_proposal (+ optional critique) into project state."""
    compact = compact_research_proposal(proposal)
    updated = dict(state)
    updated["research_proposal"] = compact
    # Reset H1 when a new proposal is attached — never inherit silent approval.
    approval_status = dict(updated.get("approval_status") or {})
    approval_status["h1"] = "pending"
    updated["approval_status"] = approval_status

    decision_report = {
        "report_version": DECISION_REPORT_VERSION,
        "proposal_id": compact.get("proposal_id"),
        "proposal_sha256": proposal_sha256(proposal),
        "h1": {
            "status": "pending",
            "auto_approved": False,
            "decided_by": None,
            "notes": "Awaiting explicit human H1 Approve / Request-revision.",
        },
        "modeling_gate": modeling_gate_status(updated).model_dump(mode="json"),
    }
    if critique is not None:
        critique_compact = compact_debate_critique(critique)
        decision_report["critique"] = critique_compact
        updated["disagreement_log"] = disagreement_log_from_critique(critique)
    else:
        # Keep prior critique only if proposal_id matches; otherwise clear.
        prior = updated.get("decision_report") or {}
        prior_critique = prior.get("critique") if isinstance(prior, dict) else None
        if (
            isinstance(prior_critique, dict)
            and prior_critique.get("proposal_id") == compact.get("proposal_id")
        ):
            decision_report["critique"] = prior_critique
        else:
            updated["disagreement_log"] = []

    updated["decision_report"] = decision_report
    phases = dict(updated.get("workspace_phases") or {})
    phases["research_strategy"] = "proposed"
    phases["h1"] = "pending"
    # Phase 6 modeling remains not implemented; gate stays blocked.
    phases["strategy_modeling"] = "blocked_until_h1"
    updated["workspace_phases"] = phases
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


def persist_critique_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    critique: DebateCritique | dict[str, Any],
    note: str = "phase5-debate-critique",
) -> dict[str, Any]:
    """Attach critique / disagreement_log without changing H1 human decision."""
    critique_compact = compact_debate_critique(critique)
    updated = dict(state)
    decision_report = dict(updated.get("decision_report") or {})
    decision_report["report_version"] = DECISION_REPORT_VERSION
    decision_report["critique"] = critique_compact
    if "h1" not in decision_report:
        decision_report["h1"] = {
            "status": (updated.get("approval_status") or {}).get("h1") or "pending",
            "auto_approved": False,
        }
    decision_report["modeling_gate"] = modeling_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision_report
    updated["disagreement_log"] = disagreement_log_from_critique(critique)
    phases = dict(updated.get("workspace_phases") or {})
    phases["debate_critic"] = "recorded"
    updated["workspace_phases"] = phases
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


def build_h1_decision(
    *,
    status: Literal["approved", "revision_requested", "rejected"],
    proposal: ResearchProposal | dict[str, Any],
    selected_candidate_id: str | None,
    notes: str = "",
    critique_id: str | None = None,
) -> H1Decision:
    """Construct a human H1 decision. Never sets auto_approved."""
    model = (
        proposal
        if isinstance(proposal, ResearchProposal)
        else ResearchProposal.model_validate(proposal)
    )
    if status == "approved":
        selected = selected_candidate_id or model.recommended_candidate_id
        if not selected:
            raise ValueError("H1 approval requires a selected candidate.")
        ids = {c.candidate_id for c in model.candidates}
        if selected not in ids:
            raise ValueError(f"selected_candidate_id '{selected}' is not in the proposal.")
    else:
        selected = selected_candidate_id
    digest = hashlib.sha256(
        f"{model.proposal_id}|{status}|{selected or ''}|{notes}".encode("utf-8")
    ).hexdigest()[:10]
    return H1Decision(
        decision_id=f"h1d_{digest}",
        status=status,
        proposal_id=model.proposal_id,
        selected_candidate_id=selected if status == "approved" else selected,
        notes=notes,
        decided_by="human",
        auto_approved=False,
        decided_at_utc=_utc_now(),
        proposal_sha256=proposal_sha256(model),
        critique_id=critique_id,
    )


def persist_h1_decision_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    decision: H1Decision | dict[str, Any],
    note: str = "phase5-h1-decision",
) -> dict[str, Any]:
    """Persist human H1 decision. Refuses auto-approval. Does not start Phase 6."""
    h1 = decision if isinstance(decision, H1Decision) else H1Decision.model_validate(decision)
    if h1.auto_approved:
        raise ValueError("H1 auto-approval is forbidden.")
    compact = compact_h1_decision(h1)
    updated = dict(state)
    approval_status = dict(updated.get("approval_status") or {})
    approval_status["h1"] = h1.status
    updated["approval_status"] = approval_status

    decision_report = dict(updated.get("decision_report") or {})
    decision_report["report_version"] = DECISION_REPORT_VERSION
    decision_report["proposal_id"] = h1.proposal_id
    decision_report["proposal_sha256"] = h1.proposal_sha256
    decision_report["h1"] = compact
    # Refresh modeling gate after writing approval_status.
    updated["decision_report"] = decision_report
    gate = modeling_gate_status(updated)
    decision_report["modeling_gate"] = gate.model_dump(mode="json")
    updated["decision_report"] = decision_report

    phases = dict(updated.get("workspace_phases") or {})
    phases["h1"] = h1.status
    if h1.status == "approved":
        phases["research_strategy"] = "h1_approved"
        # Modeling agent is still Phase 6 — keep explicit blocked-until-implemented label.
        phases["strategy_modeling"] = "h1_approved_phase6_pending"
    elif h1.status == "revision_requested":
        phases["research_strategy"] = "revision_requested"
        phases["strategy_modeling"] = "blocked_until_h1"
    else:
        phases["research_strategy"] = "h1_rejected"
        phases["strategy_modeling"] = "blocked_until_h1"
    updated["workspace_phases"] = phases

    # Never mark research_task_complete in Phase 5.
    assert_safe_for_persistence(updated, "state")

    _project, run, saved = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=updated,
        input_signature=input_signature,
        note=note,
    )
    # Record durable approval row when a run_id exists.
    run_id = run.run_id
    try:
        store.add_approval(
            make_approval(
                project_id=project_id,
                run_id=run_id,
                gate="H1",
                status=(
                    "approved"
                    if h1.status == "approved"
                    else ("rejected" if h1.status == "rejected" else "pending")
                ),
                notes=h1.notes or f"H1 {h1.status}",
                subject_sha256=h1.proposal_sha256,
            )
        )
    except Exception:
        # Local stores always support add_approval; keep state write even if row fails.
        pass

    saved = dict(saved)
    saved["run_id"] = run_id
    saved["data_resume"] = "reupload_required"
    return saved
