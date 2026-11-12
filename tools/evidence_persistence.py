"""Sanitize Literature & Evidence reports into ResearchState (Phase 4).

Persisted payloads must pass Phase 1 sanitize_state_for_persistence rules —
no secrets, no raw bytes, no invented source claims.
"""

from __future__ import annotations

from typing import Any

from core.project_store import ProjectStore
from schemas.evidence import LiteratureEvidenceReport
from schemas.persistence import assert_safe_for_persistence

EVIDENCE_REPORT_VERSION = "evidence_1.0"


def compact_evidence_report(
    report: LiteratureEvidenceReport | dict[str, Any],
) -> dict[str, Any]:
    """Return a persistence-safe dump of the literature evidence report."""
    model = (
        report
        if isinstance(report, LiteratureEvidenceReport)
        else LiteratureEvidenceReport.model_validate(report)
    )
    if model.invented_sources or any(card.invented for card in model.cards):
        raise ValueError("Refusing to persist invented literature sources.")
    payload = model.model_dump(mode="json")
    payload["report_version"] = EVIDENCE_REPORT_VERSION
    payload["invented_sources"] = False
    assert_safe_for_persistence(payload, "evidence_report")
    return payload


def citation_entries_from_report(
    report: LiteratureEvidenceReport | dict[str, Any],
) -> list[dict[str, Any]]:
    """Compact citation list for ResearchState.citations."""
    model = (
        report
        if isinstance(report, LiteratureEvidenceReport)
        else LiteratureEvidenceReport.model_validate(report)
    )
    entries: list[dict[str, Any]] = []
    for card in model.cards:
        entry = {
            "citation_key": card.citation.citation_key,
            "source_id": card.source.source_id,
            "card_id": card.card_id,
            "title": card.source.title,
            "year": card.source.year,
            "original_url": card.source.original_url,
            "local_path": card.source.local_path,
            "source_type": card.source.source_type,
            "locator_status": card.locator_status,
            "verification_status": card.verification_status,
            "citation_type": card.citation.citation_type,
        }
        assert_safe_for_persistence(entry, "citations")
        entries.append(entry)
    return entries


def persist_evidence_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    report: LiteratureEvidenceReport | dict[str, Any],
    note: str = "phase4-literature-evidence",
) -> dict[str, Any]:
    """Attach sanitized evidence_report + citations into project state."""
    compact = compact_evidence_report(report)
    citations = citation_entries_from_report(report)
    updated = dict(state)
    updated["evidence_report"] = compact
    updated["citations"] = citations
    phases = dict(updated.get("workspace_phases") or {})
    phases["literature_evidence"] = "recorded"
    updated["workspace_phases"] = phases
    # Do not claim research_task_complete or advance past data_analysis_done.
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
