"""Sanitized EDA summaries and artifact registration for ResearchState (Phase 3).

Full EDAReport payloads contain forbidden keys (sample_values, numeric_summary,
preview_rows, …). Persistence keeps compact provenance + on-disk artifact refs
only, then promotes lifecycle to data_analysis_done when appropriate.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core.lifecycle import mark_data_analysis_done
from core.project_store import ProjectStore, make_artifact, make_approval
from schemas.dataset_bundle import DatasetProfileContract
from schemas.eda_plan import ProblemAwareEDAPlan
from schemas.persistence import assert_safe_for_persistence
from schemas.relationships import JoinPreviewResult, RelationshipReport

COMPACT_EDA_VERSION = "compact_1.0"


def compact_profile_summary(profile: DatasetProfileContract) -> dict[str, Any]:
    """Sanitized independent-profile summary — no sample rows or numeric dumps."""
    context = profile.model_context()
    # model_context already omits frames; drop any residual forbidden-shaped keys.
    summary = {
        "dataset_id": context["dataset_id"],
        "project_id": context["project_id"],
        "display_name": context["display_name"],
        "file_name": context["file_name"],
        "sha256": context["sha256"],
        "row_count": context["row_count"],
        "column_count": context["column_count"],
        "qualified_columns": context["qualified_columns"],
        "columns": [
            {
                "name": column["name"],
                "qualified_name": column["qualified_name"],
                "dtype": column["dtype"],
                "missing_count": column["missing_count"],
                "unique_count": column["unique_count"],
            }
            for column in context["columns"]
        ],
        "summary": {
            key: value
            for key, value in (context.get("summary") or {}).items()
            if key
            in {
                "row_count",
                "column_count",
                "numeric_column_count",
                "columns_with_missing_values",
                "chart_plan_approval",
            }
        },
        "warnings": list(context.get("warnings") or []),
    }
    assert_safe_for_persistence(summary, "eda.profile")
    return summary


def compact_relationship_summary(
    report: RelationshipReport | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if report is None:
        return None
    model = (
        report
        if isinstance(report, RelationshipReport)
        else RelationshipReport.model_validate(report)
    )
    payload = {
        "relationship_version": model.relationship_version,
        "project_id": model.project_id,
        "dataset_ids": list(model.dataset_ids),
        "joined": False,
        "persisted": False,
        "limitations": list(model.limitations),
        "pairs": [
            {
                "left_dataset_id": pair.left_dataset_id,
                "right_dataset_id": pair.right_dataset_id,
                "left_display_name": pair.left_display_name,
                "right_display_name": pair.right_display_name,
                "verdict": pair.verdict,
                "state": pair.state,
                "can_safely_join": pair.can_safely_join,
                "caveats": list(pair.caveats),
                "candidate_count": len(pair.candidates),
            }
            for pair in model.pairs
        ],
    }
    assert_safe_for_persistence(payload, "eda.relationships")
    return payload


def compact_integration_confirmation(
    *,
    left_dataset_id: str,
    right_dataset_id: str,
    left_key: str,
    right_key: str,
    join_type: str,
    preview: JoinPreviewResult | dict[str, Any],
) -> dict[str, Any]:
    """Record that the user previewed an integration — still not a merged dataset."""
    result = (
        preview
        if isinstance(preview, JoinPreviewResult)
        else JoinPreviewResult.model_validate(preview)
    )
    payload = {
        "confirmed": True,
        "merged": False,
        "joined": False,
        "left_dataset_id": left_dataset_id,
        "right_dataset_id": right_dataset_id,
        "left_key": left_key,
        "right_key": right_key,
        "join_type": join_type,
        "status": result.status,
        "reason": result.reason,
        "message": result.message,
        "warnings": list(result.warnings),
        "unmatched_left_rows": result.unmatched_left_rows,
        "unmatched_right_rows": result.unmatched_right_rows,
        "overlap_key_count": result.overlap_key_count,
        "cardinality": result.cardinality,
        "output_row_count": result.output_row_count,
        "output_column_count": result.output_column_count,
    }
    assert_safe_for_persistence(payload, "eda.integration_confirmation")
    return payload


def build_compact_eda_report(
    *,
    project_id: str,
    bundle_fingerprint: str | None,
    profiles: list[DatasetProfileContract] | list[dict[str, Any]],
    plan: ProblemAwareEDAPlan | dict[str, Any] | None = None,
    relationship_summary: dict[str, Any] | None = None,
    artifact_refs: list[dict[str, Any]] | None = None,
    integration_confirmation: dict[str, Any] | None = None,
    mode: str = "independent",
) -> dict[str, Any]:
    dataset_summaries: list[dict[str, Any]] = []
    for item in profiles:
        if isinstance(item, DatasetProfileContract):
            dataset_summaries.append(compact_profile_summary(item))
        else:
            assert_safe_for_persistence(item, "eda.profile")
            dataset_summaries.append(item)

    plan_payload: dict[str, Any] | None
    if plan is None:
        plan_payload = None
    elif isinstance(plan, ProblemAwareEDAPlan):
        plan_payload = plan.model_dump(mode="json")
    else:
        plan_payload = dict(plan)

    payload: dict[str, Any] = {
        "report_version": COMPACT_EDA_VERSION,
        "project_id": project_id,
        "mode": mode,
        "bundle_fingerprint": bundle_fingerprint,
        "datasets": dataset_summaries,
        "problem_aware_plan": plan_payload,
        "relationships": relationship_summary,
        "artifact_refs": list(artifact_refs or []),
        "integration_confirmation": integration_confirmation,
        "joined": False,
        "raw_rows_included": False,
        "file_bytes_included": False,
    }
    assert_safe_for_persistence(payload, "eda_report")
    return payload


def register_eda_artifacts(
    store: ProjectStore,
    *,
    project_id: str,
    run_id: str,
    artifacts: dict[str, Any],
    dataset_sha256: str | None = None,
    label_prefix: str = "EDA",
) -> list[dict[str, Any]]:
    """Write ArtifactRefRecord entries for on-disk EDA outputs. Returns compact refs."""
    refs: list[dict[str, Any]] = []
    pairs: list[tuple[str, str, str]] = []
    report_json = artifacts.get("report_json_path")
    report_md = artifacts.get("report_markdown_path")
    if isinstance(report_json, str):
        pairs.append(("eda_report_json", report_json, f"{label_prefix} JSON"))
    if isinstance(report_md, str):
        pairs.append(("eda_report_markdown", report_md, f"{label_prefix} Markdown"))
    for chart_path in artifacts.get("chart_paths") or []:
        if isinstance(chart_path, str):
            pairs.append(("eda_chart", chart_path, f"{label_prefix} chart"))

    for kind, uri, label in pairs:
        digest = _file_sha256(uri)
        record = store.add_artifact(
            make_artifact(
                project_id=project_id,
                run_id=run_id,
                kind=kind,
                uri=uri,
                sha256=digest,
                label=label,
                metadata={
                    "dataset_sha256": dataset_sha256,
                    "joined": False,
                },
            )
        )
        refs.append(
            {
                "artifact_id": record.artifact_id,
                "kind": record.kind,
                "uri": record.uri,
                "sha256": record.sha256,
                "label": record.label,
            }
        )
    assert_safe_for_persistence(refs, "eda.artifact_refs")
    return refs


def persist_approved_eda_into_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    compact_eda: dict[str, Any],
    artifacts: dict[str, Any] | None = None,
    dataset_sha256: str | None = None,
    note: str = "phase3-approved-eda",
) -> dict[str, Any]:
    """Merge compact EDA into ResearchState, register artifacts, mark data_analysis_done."""
    assert_safe_for_persistence(compact_eda, "eda_report")
    updated = dict(state)
    run_id = updated.get("run_id")
    artifact_refs: list[dict[str, Any]] = list(
        (compact_eda.get("artifact_refs") or [])
        if isinstance(compact_eda.get("artifact_refs"), list)
        else []
    )
    if artifacts and run_id:
        artifact_refs = register_eda_artifacts(
            store,
            project_id=project_id,
            run_id=str(run_id),
            artifacts=artifacts,
            dataset_sha256=dataset_sha256,
        )
        compact_eda = dict(compact_eda)
        compact_eda["artifact_refs"] = artifact_refs
        assert_safe_for_persistence(compact_eda, "eda_report")

    updated["eda_report"] = compact_eda
    if run_id and dataset_sha256:
        store.add_approval(
            make_approval(
                project_id=project_id,
                run_id=str(run_id),
                gate="chart_plan",
                status="approved",
                notes="Approved independent EDA / chart plan (Phase 3).",
                subject_sha256=dataset_sha256,
            )
        )
        approval_status = dict(updated.get("approval_status") or {})
        approval_status["chart_plan"] = "approved"
        updated["approval_status"] = approval_status

    updated = mark_data_analysis_done(updated)
    phases = dict(updated.get("workspace_phases") or {})
    phases["independent_eda"] = "done"
    updated["workspace_phases"] = phases

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


def _file_sha256(path: str) -> str | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
