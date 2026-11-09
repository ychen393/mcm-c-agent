"""Streamlit-free workspace for 1–5 independent dataset profiles.

The UI calls this module after a user selects files. It does not join frames,
call a model, or build a chart that reads more than one dataset.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from schemas.dataset_bundle import DatasetProfileContract, DatasetRef
from tools.dataset_bundle import DatasetBundle, build_bundle_profiles, build_dataset_bundle

ANALYTICAL_SCOPE_INDEPENDENT = "independent"
UploadPayload = tuple[str, bytes]


@dataclass(frozen=True)
class DatasetWorkspace:
    """Loaded files plus the per-dataset views the UI renders."""

    bundle: DatasetBundle
    profiles: dict[str, DatasetProfileContract]
    views: list[dict]
    chart_planning_allowed: bool
    approval_identity: str | None


def chart_planning_allowed(dataset_count: int) -> bool:
    """Chart planning stays on the existing single-file path."""
    return dataset_count == 1


def approval_identity(dataset_count: int, single_sha256: str | None) -> str | None:
    """Identity used to invalidate a pending chart plan.

    One file keeps the file SHA-256 used by the existing approval gate.
    Two or more files cannot approve a chart plan in this slice.
    """
    if dataset_count == 1:
        if not single_sha256:
            raise ValueError("A single dataset workspace requires its SHA-256.")
        return single_sha256
    return None


def pending_plan_matches(stored_identity: str | None, current_identity: str | None) -> bool:
    """True only when a stored plan still belongs to the current single dataset."""
    return bool(stored_identity) and stored_identity == current_identity


def open_workspace(
    uploads: list[UploadPayload],
    *,
    project_id: str,
    column_units_by_dataset: Mapping[str, Mapping[str, str]] | None = None,
    data_source_by_dataset: Mapping[str, str | None] | None = None,
    temporal_frequency_by_dataset: Mapping[str, str | None] | None = None,
) -> DatasetWorkspace:
    """Load uploads through the dataset-bundle registry and describe each file."""
    bundle = build_dataset_bundle(uploads, project_id=project_id)
    profiles = build_bundle_profiles(
        bundle,
        column_units_by_dataset=column_units_by_dataset,
        data_source_by_dataset=data_source_by_dataset,
        temporal_frequency_by_dataset=temporal_frequency_by_dataset,
    )
    views = [
        describe_independent_eda(ref, profiles[ref.dataset_id]) for ref in bundle.datasets
    ]
    count = len(bundle.datasets)
    single_sha = bundle.datasets[0].sha256 if count == 1 else None
    return DatasetWorkspace(
        bundle=bundle,
        profiles=profiles,
        views=views,
        chart_planning_allowed=chart_planning_allowed(count),
        approval_identity=approval_identity(count, single_sha),
    )


def describe_independent_eda(ref: DatasetRef, profile: DatasetProfileContract) -> dict:
    """One dataset's profile for display. Omits the frame and the raw file bytes."""
    if profile.dataset_id != ref.dataset_id:
        raise ValueError("Profile dataset ID does not match the dataset reference.")
    report = profile.report
    dataset = report.dataset
    if len(dataset.columns) != len(ref.qualified_column_names):
        raise ValueError("Qualified column names must align with the profile columns.")
    name_to_qualified = {
        column.name: qualified
        for column, qualified in zip(dataset.columns, ref.qualified_column_names, strict=True)
    }
    columns = []
    for column, qualified in zip(dataset.columns, ref.qualified_column_names, strict=True):
        columns.append(
            {
                "qualified_name": qualified,
                "name": column.name,
                "dtype": column.dtype,
                "missing_count": column.missing_count,
                "missing_rate": column.missing_rate,
                "unique_count": column.unique_count,
                "unit": column.unit,
                "numeric_summary": column.numeric_summary,
            }
        )
    correlations = {
        name_to_qualified[row]: {
            name_to_qualified[column]: value for column, value in values.items()
        }
        for row, values in report.numeric_correlations.items()
    }
    return {
        "analytical_scope": ANALYTICAL_SCOPE_INDEPENDENT,
        "joined": False,
        "dataset_id": ref.dataset_id,
        "display_name": ref.display_name,
        "file_name": ref.file_name,
        "sha256": ref.sha256,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "summary": report.summary,
        "warnings": list(report.warnings),
        "columns": columns,
        "correlations_within_dataset": correlations,
        "data_source": dataset.data_source,
        "temporal_frequency": dataset.temporal_frequency,
        "inferred_frequency": dataset.inferred_frequency,
        "period_start": dataset.period_start,
        "period_end": dataset.period_end,
    }
