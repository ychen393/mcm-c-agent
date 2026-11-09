"""Deterministic relationship evidence and an explicit join preview.

Column statistics are computed from value counts. The frames are not joined
until ``preview_join`` runs, and that preview is neither saved nor written back
onto the source bundle.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from schemas.relationships import (
    JOIN_TYPES,
    MAX_JOIN_COLUMNS,
    MAX_JOIN_ROWS,
    MAX_PREVIEW_ROWS,
    RELATIONSHIP_LIMITATIONS,
    JoinLineage,
    JoinPreviewResult,
    KeyEvidence,
    PairRelationship,
    RelationshipReport,
)
from tools.dataset_bundle import DatasetBundle
from tools.eda_engine import infer_temporal_frequency

_DATE_KINDS = {
    "iso_date",
    "iso_datetime",
    "iso_datetime_tz",
    "datetime",
    "datetime_tz",
}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
_FREQUENCY_CLASSES = (
    ("daily", ("business-day", "daily")),
    ("weekly", ("weekly",)),
    ("monthly", ("monthly",)),
    ("quarterly", ("quarter",)),
    ("annual", ("annual", "yearly")),
    ("irregular", ("irregular", "sparse")),
)


def profile_relationships(
    bundle: DatasetBundle,
    *,
    column_units_by_dataset: dict[str, dict[str, str]] | None = None,
    temporal_frequency_by_dataset: dict[str, str | None] | None = None,
) -> RelationshipReport:
    """Describe every dataset pair without joining, resampling, or saving."""
    refs = list(bundle.datasets)
    if len(refs) < 2:
        raise ValueError("Relationship evidence needs at least two datasets.")
    units = column_units_by_dataset or {}
    frequencies = temporal_frequency_by_dataset or {}
    _reject_unknown_ids(units, frequencies, {ref.dataset_id for ref in refs})
    pairs: list[PairRelationship] = []
    for index, left in enumerate(refs):
        left_frame = bundle.loaded_dataset(left.dataset_id).frame
        for right in refs[index + 1 :]:
            right_frame = bundle.loaded_dataset(right.dataset_id).frame
            pairs.append(_profile_pair(left, right, left_frame, right_frame, units, frequencies))
    return RelationshipReport(
        project_id=bundle.project_id,
        dataset_ids=[ref.dataset_id for ref in refs],
        pairs=pairs,
        limitations=list(RELATIONSHIP_LIMITATIONS),
    )


def preview_join(
    bundle: DatasetBundle,
    *,
    left_dataset_id: str,
    right_dataset_id: str,
    left_key: str,
    right_key: str,
    join_type: str,
    column_units_by_dataset: dict[str, dict[str, str]] | None = None,
    temporal_frequency_by_dataset: dict[str, str | None] | None = None,
    max_preview_rows: int = MAX_PREVIEW_ROWS,
    max_join_rows: int = MAX_JOIN_ROWS,
    max_join_columns: int = MAX_JOIN_COLUMNS,
) -> JoinPreviewResult:
    """Return a bounded preview or a refusal. Source frames are not modified."""
    if max_preview_rows < 1 or max_join_rows < 1 or max_join_columns < 1:
        raise ValueError("Preview caps must be positive.")
    units = column_units_by_dataset or {}
    frequencies = temporal_frequency_by_dataset or {}
    _reject_unknown_ids(units, frequencies, {ref.dataset_id for ref in bundle.datasets})
    left_ref = _find_ref(bundle, left_dataset_id)
    right_ref = _find_ref(bundle, right_dataset_id)
    if left_ref is None or right_ref is None:
        missing = left_dataset_id if left_ref is None else right_dataset_id
        return _blocked(
            "unknown_dataset",
            f"The join was refused because dataset '{missing}' is not in this bundle.",
        )
    lineage = _lineage(left_ref, right_ref, left_key, right_key, _normalize_join(join_type))
    if left_ref.dataset_id == right_ref.dataset_id:
        return _blocked(
            "same_dataset",
            "The join was refused because both sides refer to the same dataset.",
            lineage=lineage,
        )
    normalized = _normalize_join(join_type)
    if normalized is None:
        return _blocked(
            "invalid_join_strategy",
            "The join was refused because the join strategy is not one of "
            "inner, left, right, or outer.",
            lineage=lineage,
        )
    lineage = _lineage(left_ref, right_ref, str(left_key), str(right_key), normalized)
    if not isinstance(left_key, str) or left_key not in left_ref.column_names:
        return _blocked(
            "untrusted_key",
            "The join was refused because the left key is not a column of the left dataset.",
            lineage=lineage,
        )
    if not isinstance(right_key, str) or right_key not in right_ref.column_names:
        return _blocked(
            "untrusted_key",
            "The join was refused because the right key is not a column of the right dataset.",
            lineage=lineage,
        )

    left_frame = bundle.loaded_dataset(left_ref.dataset_id).frame
    right_frame = bundle.loaded_dataset(right_ref.dataset_id).frame
    evidence = _describe_columns(
        left_ref,
        right_ref,
        left_frame,
        right_frame,
        left_key,
        right_key,
        units,
        frequencies,
        max_join_rows=max_join_rows,
        max_join_columns=max_join_columns,
    )
    refusal = _refusal_for(
        evidence,
        normalized,
        max_join_rows,
        max_join_columns,
        len(left_frame.columns),
        len(right_frame.columns),
    )
    if refusal is not None:
        reason, message = refusal
        return _blocked(
            reason, message, lineage=lineage, evidence=evidence, caveats=evidence.caveats
        )

    warnings = _preview_warnings(left_ref, right_ref, left_key, right_key, evidence, units)
    left_copy = left_frame.copy(deep=True)
    right_copy = right_frame.copy(deep=True)
    left_copy.columns = [f"{left_ref.dataset_id}.{column}" for column in left_copy.columns]
    right_copy.columns = [f"{right_ref.dataset_id}.{column}" for column in right_copy.columns]
    merged = left_copy.merge(
        right_copy,
        how=normalized,
        left_on=evidence.left_qualified_column,
        right_on=evidence.right_qualified_column,
        sort=False,
    )
    expected = _estimated_rows(evidence, normalized)
    if len(merged) != expected or merged.columns.duplicated().any():
        return _blocked(
            "cannot_safely_join",
            "cannot safely join: the preview row count did not match the pre-join "
            "estimate. The files were not merged.",
            lineage=lineage,
            evidence=evidence,
            caveats=evidence.caveats,
        )
    output_rows = int(len(merged))
    output_columns = int(len(merged.columns))
    preview_rows, preview_columns = _records(merged, max_preview_rows)
    truncated = len(preview_rows) < output_rows
    if truncated:
        warnings.append(
            f"Showing {len(preview_rows)} of {output_rows} rows. "
            "This preview is not a saved dataset."
        )
    warnings.append("Source files were not changed. This preview is not saved.")
    return JoinPreviewResult(
        status="preview",
        reason=None,
        message=(
            f"Preview of {normalized} join on {evidence.left_qualified_column} = "
            f"{evidence.right_qualified_column}. Source files were not changed."
        ),
        warnings=warnings,
        caveats=evidence.caveats,
        lineage=lineage,
        preview_rows=preview_rows,
        preview_columns=preview_columns,
        preview_row_count=len(preview_rows),
        output_row_count=output_rows,
        output_column_count=output_columns,
        truncated=truncated,
        unmatched_left_rows=evidence.left_unmatched_row_count,
        unmatched_right_rows=evidence.right_unmatched_row_count,
        overlap_key_count=evidence.overlap_key_count,
        cardinality=evidence.cardinality,
    )


def relationship_table_rows(report: RelationshipReport) -> list[dict[str, Any]]:
    """Flat evidence rows for the multi-dataset table."""
    rows: list[dict[str, Any]] = []
    for pair in report.pairs:
        if not pair.candidates:
            rows.append(_empty_pair_row(pair))
            continue
        for candidate in pair.candidates:
            rows.append(
                {
                    "Left dataset": pair.left_display_name,
                    "Right dataset": pair.right_display_name,
                    "Left key": candidate.left_column,
                    "Right key": candidate.right_column,
                    "Qualified left key": candidate.left_qualified_column,
                    "Qualified right key": candidate.right_qualified_column,
                    "Cardinality": candidate.cardinality,
                    "Overlap keys": candidate.overlap_key_count,
                    "Left unique": candidate.left_unique_count,
                    "Right unique": candidate.right_unique_count,
                    "Left duplicate keys": candidate.left_duplicate_key_count,
                    "Right duplicate keys": candidate.right_duplicate_key_count,
                    "Left null rate": candidate.left_null_rate,
                    "Right null rate": candidate.right_null_rate,
                    "Left unmatched rows": candidate.left_unmatched_row_count,
                    "Right unmatched rows": candidate.right_unmatched_row_count,
                    "Estimated inner rows": candidate.estimated_inner_rows,
                    "Frequency": _frequency_cell(candidate),
                    "Safe to preview": "yes" if candidate.safe_to_preview else "no",
                    "State": "candidate" if candidate.safe_to_preview else "cannot safely join",
                    "Caveats": "; ".join(candidate.caveats),
                }
            )
    return rows


def _profile_pair(left, right, left_frame, right_frame, units, frequencies) -> PairRelationship:
    shared = [name for name in left.column_names if name in set(right.column_names)]
    candidates = [
        _describe_columns(left, right, left_frame, right_frame, name, name, units, frequencies)
        for name in shared
    ]
    cross, date_caveat = _cross_date_candidate(
        left, right, left_frame, right_frame, shared, units, frequencies
    )
    if cross is not None:
        candidates.append(cross)
    caveats: list[str] = []
    if date_caveat:
        caveats.append(date_caveat)
    caveats.extend(_same_name_unit_notes(left, right, units))
    verdict, state, safe, decision_caveats = _pair_decision(candidates, bool(date_caveat))
    caveats.extend(decision_caveats)
    return PairRelationship(
        left_dataset_id=left.dataset_id,
        right_dataset_id=right.dataset_id,
        left_display_name=left.display_name,
        right_display_name=right.display_name,
        left_sha256=left.sha256,
        right_sha256=right.sha256,
        verdict=verdict,
        can_safely_join=safe and verdict != "UNKNOWN",
        state=state,
        caveats=_unique(caveats),
        candidates=candidates,
    )


def _describe_columns(
    left,
    right,
    left_frame: pd.DataFrame,
    right_frame: pd.DataFrame,
    left_column: str,
    right_column: str,
    units,
    frequencies,
    *,
    max_join_rows: int = MAX_JOIN_ROWS,
    max_join_columns: int = MAX_JOIN_COLUMNS,
) -> KeyEvidence:
    left_series = left_frame[left_column]
    right_series = right_frame[right_column]
    left_kind = _series_kind(left_series)
    right_kind = _series_kind(right_series)
    compatible = _kinds_compatible(left_kind, right_kind, left_series, right_series)
    left_counts, left_nulls = _value_counts(left_series)
    right_counts, right_nulls = _value_counts(right_series)
    left_rows = int(len(left_series))
    right_rows = int(len(right_series))
    if compatible:
        overlap_stats = _overlap(left_counts, right_counts, left_nulls, right_nulls)
    else:
        overlap_stats = {
            "overlap_key_count": 0,
            "left_unmatched_key_count": len(left_counts),
            "right_unmatched_key_count": len(right_counts),
            "left_unmatched_row_count": left_rows - left_nulls,
            "right_unmatched_row_count": right_rows - right_nulls,
            "cardinality": "UNKNOWN",
            "estimated_inner_rows": 0,
            "estimated_left_rows": 0,
            "estimated_right_rows": 0,
            "estimated_outer_rows": 0,
        }
    left_frequency, right_frequency, mixed, frequency_caveats = _frequency_status(
        left_series,
        right_series,
        left_kind,
        right_kind,
        left.dataset_id,
        right.dataset_id,
        frequencies,
    )
    left_unit = _unit(units, left.dataset_id, left_column)
    right_unit = _unit(units, right.dataset_id, right_column)
    unit_conflict = bool(left_unit and right_unit and left_unit != right_unit)
    column_count = int(left_frame.shape[1] + right_frame.shape[1])
    estimates = (
        overlap_stats["estimated_inner_rows"],
        overlap_stats["estimated_left_rows"],
        overlap_stats["estimated_right_rows"],
        overlap_stats["estimated_outer_rows"],
    )
    oversized = column_count > max_join_columns or any(value > max_join_rows for value in estimates)
    cardinality = overlap_stats["cardinality"]
    caveats = _candidate_caveats(
        compatible=compatible,
        unit_conflict=unit_conflict,
        left_unit=left_unit,
        right_unit=right_unit,
        mixed=mixed,
        frequency_caveats=frequency_caveats,
        cardinality=cardinality,
        left_nulls=left_nulls,
        right_nulls=right_nulls,
        left_duplicate=_duplicate_key_count(left_counts),
        right_duplicate=_duplicate_key_count(right_counts),
        oversized=oversized,
        left_kind=left_kind,
        right_kind=right_kind,
    )
    safe = (
        compatible
        and not unit_conflict
        and not mixed
        and not oversized
        and cardinality in {"ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE"}
        and overlap_stats["overlap_key_count"] > 0
    )
    return KeyEvidence(
        left_dataset_id=left.dataset_id,
        right_dataset_id=right.dataset_id,
        left_column=left_column,
        right_column=right_column,
        left_qualified_column=f"{left.dataset_id}.{left_column}",
        right_qualified_column=f"{right.dataset_id}.{right_column}",
        left_dtype=str(left_series.dtype),
        right_dtype=str(right_series.dtype),
        left_null_count=left_nulls,
        right_null_count=right_nulls,
        left_null_rate=_rate(left_nulls, left_rows),
        right_null_rate=_rate(right_nulls, right_rows),
        left_unique_count=len(left_counts),
        right_unique_count=len(right_counts),
        left_duplicate_key_count=_duplicate_key_count(left_counts),
        right_duplicate_key_count=_duplicate_key_count(right_counts),
        left_rows_in_duplicate_keys=_rows_in_duplicate_keys(left_counts),
        right_rows_in_duplicate_keys=_rows_in_duplicate_keys(right_counts),
        left_overlap_rate=_optional_rate(overlap_stats["overlap_key_count"], len(left_counts)),
        right_overlap_rate=_optional_rate(overlap_stats["overlap_key_count"], len(right_counts)),
        mixed_frequency=mixed,
        dtype_compatible=compatible,
        unit_conflict=unit_conflict,
        caveats=caveats,
        safe_to_preview=safe,
        left_frequency=left_frequency,
        right_frequency=right_frequency,
        **overlap_stats,
    )


def _pair_decision(candidates: list[KeyEvidence], ambiguous_dates: bool):
    """Pick a pair verdict from evidence. Two overlapping keys stay UNKNOWN."""
    if not candidates and ambiguous_dates:
        return (
            "UNKNOWN",
            "ambiguous",
            False,
            ["UNKNOWN until you choose the date columns. Nothing is joined automatically."],
        )
    if not candidates:
        return (
            "UNRELATED",
            "cannot safely join",
            False,
            ["No exact shared column and no single exact date pair. cannot safely join."],
        )
    plausible = [
        item
        for item in candidates
        if item.dtype_compatible and not item.unit_conflict and item.overlap_key_count > 0
    ]
    if len(plausible) > 1:
        return (
            "UNKNOWN",
            "ambiguous",
            False,
            [
                "UNKNOWN: more than one possible key. Choose a key explicitly. "
                "Nothing is joined automatically."
            ],
        )
    if len(plausible) == 1:
        chosen = plausible[0]
        if chosen.mixed_frequency or not chosen.safe_to_preview:
            verdict = (
                "UNKNOWN"
                if chosen.mixed_frequency or chosen.cardinality == "UNKNOWN"
                else chosen.cardinality
            )
            return (
                verdict,
                "cannot safely join",
                False,
                ["cannot safely join on this key.", *chosen.caveats],
            )
        return chosen.cardinality, "candidate", True, list(chosen.caveats)
    if len(candidates) == 1:
        only = candidates[0]
        verdict = "UNKNOWN" if only.cardinality == "UNKNOWN" else only.cardinality
        return (
            verdict,
            "cannot safely join",
            False,
            ["cannot safely join on this key.", *only.caveats],
        )
    return (
        "UNKNOWN",
        "cannot safely join",
        False,
        ["UNKNOWN: none of the shared columns is a safe key. cannot safely join."],
    )


def _cross_date_candidate(left, right, left_frame, right_frame, shared, units, frequencies):
    left_dates = _date_columns(left, left_frame)
    right_dates = _date_columns(right, right_frame)
    left_unpaired = [name for name in left_dates if name not in shared]
    right_unpaired = [name for name in right_dates if name not in shared]
    if len(left_unpaired) > 1 or len(right_unpaired) > 1:
        names = ", ".join(left_unpaired + right_unpaired)
        return None, (
            f"UNKNOWN: more than one unpaired date column ({names}). No date pair was guessed."
        )
    if len(left_unpaired) == 1 and len(right_unpaired) == 1:
        evidence = _describe_columns(
            left,
            right,
            left_frame,
            right_frame,
            left_unpaired[0],
            right_unpaired[0],
            units,
            frequencies,
        )
        return evidence, None
    return None, None


def _date_columns(ref, frame: pd.DataFrame) -> list[str]:
    return [name for name in ref.column_names if _series_kind(frame[name]) in _DATE_KINDS]


def _overlap(left_counts: dict, right_counts: dict, left_nulls: int, right_nulls: int) -> dict:
    shared = [key for key in left_counts if key in right_counts]
    inner = sum(left_counts[key] * right_counts[key] for key in shared)
    left_only_rows = sum(left_counts[key] for key in left_counts if key not in right_counts)
    right_only_rows = sum(right_counts[key] for key in right_counts if key not in left_counts)
    both_multi = any(left_counts[key] > 1 and right_counts[key] > 1 for key in shared)
    left_multi = any(left_counts[key] > 1 for key in shared)
    right_multi = any(right_counts[key] > 1 for key in shared)
    if not shared:
        cardinality = "NO_OVERLAP"
    elif both_multi:
        cardinality = "MANY_TO_MANY"
    elif left_multi:
        cardinality = "MANY_TO_ONE"
    elif right_multi:
        cardinality = "ONE_TO_MANY"
    else:
        cardinality = "ONE_TO_ONE"
    return {
        "overlap_key_count": len(shared),
        "left_unmatched_key_count": sum(1 for key in left_counts if key not in right_counts),
        "right_unmatched_key_count": sum(1 for key in right_counts if key not in left_counts),
        "left_unmatched_row_count": left_only_rows,
        "right_unmatched_row_count": right_only_rows,
        "cardinality": cardinality,
        "estimated_inner_rows": inner,
        "estimated_left_rows": inner + left_only_rows + left_nulls,
        "estimated_right_rows": inner + right_only_rows + right_nulls,
        "estimated_outer_rows": inner + left_only_rows + right_only_rows + left_nulls + right_nulls,
    }


def _frequency_status(
    left_series, right_series, left_kind, right_kind, left_id, right_id, frequencies
):
    caveats: list[str] = []
    if left_kind not in _DATE_KINDS or right_kind not in _DATE_KINDS:
        return None, None, False, caveats
    left_inferred = _inferred_frequency(left_series, left_kind)
    right_inferred = _inferred_frequency(right_series, right_kind)
    left_declared = _declared(frequencies, left_id)
    right_declared = _declared(frequencies, right_id)
    left_class = frequency_class(left_declared) or frequency_class(left_inferred)
    right_class = frequency_class(right_declared) or frequency_class(right_inferred)
    if _internal_frequency_conflict(left_declared, left_inferred):
        caveats.append(
            "Declared frequency disagrees with the estimated date interval. "
            "Values were not resampled."
        )
    if _internal_frequency_conflict(right_declared, right_inferred):
        caveats.append(
            "Declared frequency disagrees with the estimated date interval. "
            "Values were not resampled."
        )
    mixed = bool(caveats or (left_class and right_class and left_class != right_class))
    if mixed and left_class != right_class:
        caveats.append(
            f"Date frequencies differ ({left_class or 'unknown'} vs {right_class or 'unknown'}). "
            "Values were not resampled or aligned."
        )
    elif not left_class or not right_class:
        caveats.append(
            "Frequency could not be estimated from these dates. No alignment was applied."
        )
    if left_kind in {"datetime_tz", "iso_datetime_tz"} or right_kind in {
        "datetime_tz",
        "iso_datetime_tz",
    }:
        caveats.append("Time-zone-bearing values were not converted.")
    return (
        left_declared or left_inferred,
        right_declared or right_inferred,
        mixed,
        _unique(caveats),
    )


def _candidate_caveats(**flags) -> list[str]:
    caveats: list[str] = []
    if not flags["compatible"]:
        caveats.append(
            f"Column types differ ({flags['left_kind']} vs {flags['right_kind']}) "
            "and were not coerced."
        )
    if flags["unit_conflict"]:
        caveats.append(
            f"Key units differ ({flags['left_unit']} vs {flags['right_unit']}) "
            "and were not converted."
        )
    caveats.extend(flags["frequency_caveats"])
    cardinality = flags["cardinality"]
    if cardinality == "NO_OVERLAP":
        caveats.append("No overlapping non-null values.")
    elif cardinality == "MANY_TO_MANY":
        caveats.append("Duplicate keys on both sides would multiply rows.")
    elif cardinality in {"ONE_TO_MANY", "MANY_TO_ONE"}:
        caveats.append("Duplicate keys multiply rows and were not aggregated.")
    if flags["left_nulls"] or flags["right_nulls"]:
        caveats.append("Null keys are unmatched and were not imputed.")
    if flags["oversized"]:
        caveats.append("The estimated result exceeds the preview row or column cap.")
    if cardinality == "ONE_TO_ONE" and (flags["left_duplicate"] or flags["right_duplicate"]):
        caveats.append("Duplicate keys fall outside the overlap and were not aggregated.")
    return _unique(caveats)


def _refusal_for(
    evidence: KeyEvidence,
    join_type: str,
    max_join_rows: int,
    max_join_columns: int,
    left_columns: int,
    right_columns: int,
):
    if not evidence.dtype_compatible:
        return (
            "incompatible_dtype",
            "cannot safely join: column types are incompatible and were not coerced.",
        )
    if evidence.unit_conflict:
        return (
            "unit_mismatch",
            "cannot safely join: key units differ and were not converted.",
        )
    if evidence.mixed_frequency:
        return (
            "frequency_mismatch",
            "cannot safely join: date frequencies differ "
            f"({evidence.left_frequency or 'unknown'} vs {evidence.right_frequency or 'unknown'}). "
            "Rows were not resampled or aligned.",
        )
    if evidence.overlap_key_count < 1:
        return (
            "cannot_safely_join",
            "cannot safely join: the selected keys have no overlapping values. "
            "The files were not merged.",
        )
    if evidence.cardinality == "MANY_TO_MANY":
        return (
            "many_to_many",
            "cannot safely join: many-to-many duplicate keys would multiply rows. "
            "The join was not run.",
        )
    estimated = _estimated_rows(evidence, join_type)
    column_count = left_columns + right_columns
    if estimated > max_join_rows or column_count > max_join_columns:
        return (
            "oversized_result",
            "The join was refused because the estimated result has "
            f"{estimated:,} rows and {column_count} columns, above the "
            f"{max_join_rows:,} row / {max_join_columns} column preview cap. "
            "The files were not merged.",
        )
    return None


def _preview_warnings(left, right, left_key, right_key, evidence: KeyEvidence, units) -> list[str]:
    warnings: list[str] = []
    if evidence.cardinality in {"ONE_TO_MANY", "MANY_TO_ONE"}:
        warnings.append("Duplicate keys multiply preview rows. Values were not aggregated.")
    if evidence.left_unmatched_row_count or evidence.right_unmatched_row_count:
        warnings.append(
            "Unmatched rows stay unmatched "
            f"(left {evidence.left_unmatched_row_count}, "
            f"right {evidence.right_unmatched_row_count}). "
            "Missing keys were not imputed."
        )
    if evidence.left_null_count or evidence.right_null_count:
        warnings.append("Null keys were left unmatched and were not imputed.")
    shared = [name for name in left.column_names if name in set(right.column_names)]
    others = sorted(name for name in shared if name not in {left_key, right_key})
    if others:
        warnings.append(
            "Same-name fields remain scoped to each dataset and were not merged: "
            + ", ".join(others)
            + "."
        )
    for name in shared:
        if name in {left_key, right_key} and left_key == right_key:
            continue
        left_unit = _unit(units, left.dataset_id, name)
        right_unit = _unit(units, right.dataset_id, name)
        if left_unit and right_unit and left_unit != right_unit:
            warnings.append(
                f"Same-name field {name} keeps both units ({left_unit} vs {right_unit}) "
                "and was not converted."
            )
    return _unique(warnings)


def _empty_pair_row(pair: PairRelationship) -> dict[str, Any]:
    return {
        "Left dataset": pair.left_display_name,
        "Right dataset": pair.right_display_name,
        "Left key": "—",
        "Right key": "—",
        "Qualified left key": "—",
        "Qualified right key": "—",
        "Cardinality": pair.verdict,
        "Overlap keys": 0,
        "Left unique": 0,
        "Right unique": 0,
        "Left duplicate keys": 0,
        "Right duplicate keys": 0,
        "Left null rate": 0,
        "Right null rate": 0,
        "Left unmatched rows": 0,
        "Right unmatched rows": 0,
        "Estimated inner rows": 0,
        "Frequency": "—",
        "Safe to preview": "no",
        "State": pair.state,
        "Caveats": "; ".join(pair.caveats),
    }


def _blocked(
    reason: str,
    message: str,
    *,
    lineage=None,
    evidence: KeyEvidence | None = None,
    caveats=None,
    warnings=None,
) -> JoinPreviewResult:
    return JoinPreviewResult(
        status="blocked",
        reason=reason,
        message=message,
        warnings=list(warnings or []),
        caveats=list(caveats or []),
        lineage=lineage,
        preview_rows=[],
        preview_columns=[],
        preview_row_count=0,
        output_row_count=None,
        output_column_count=None,
        truncated=False,
        unmatched_left_rows=None if evidence is None else evidence.left_unmatched_row_count,
        unmatched_right_rows=None if evidence is None else evidence.right_unmatched_row_count,
        overlap_key_count=None if evidence is None else evidence.overlap_key_count,
        cardinality=None if evidence is None else evidence.cardinality,
    )


def _lineage(left, right, left_key: str, right_key: str, join_type: str | None) -> JoinLineage:
    return JoinLineage(
        left_dataset_id=left.dataset_id,
        right_dataset_id=right.dataset_id,
        left_file_name=left.file_name,
        right_file_name=right.file_name,
        left_sha256=left.sha256,
        right_sha256=right.sha256,
        left_column=left_key,
        right_column=right_key,
        left_qualified_key=f"{left.dataset_id}.{left_key}",
        right_qualified_key=f"{right.dataset_id}.{right_key}",
        join_type=join_type or "invalid",
    )


def _records(frame: pd.DataFrame, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    shown = frame.head(limit)
    columns = [str(column) for column in shown.columns]
    rows = [
        {str(key): _json_scalar(value) for key, value in record.items()}
        for record in shown.to_dict(orient="records")
    ]
    return rows, columns


def _json_scalar(value: Any) -> Any:
    if value is None or _missing(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if math.isnan(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _value_counts(series: pd.Series) -> tuple[dict[Any, int], int]:
    counts: dict[Any, int] = {}
    nulls = 0
    for value in series.tolist():
        if _missing(value):
            nulls += 1
            continue
        key = _canonical(value)
        counts[key] = counts.get(key, 0) + 1
    return counts, nulls


def _canonical(value: Any) -> tuple:
    if isinstance(value, (bool, np.bool_)):
        return ("bool", bool(value))
    if isinstance(value, (int, np.integer)):
        return ("num", int(value))
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isfinite(number) and number.is_integer() and abs(number) < 2**53:
            return ("num", int(number))
        return ("num", number)
    if isinstance(value, (pd.Timestamp, datetime)):
        aware = value.tzinfo is not None
        return ("dt_tz" if aware else "dt", value.isoformat())
    return ("str", str(value))


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return False
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, (bool, np.bool_)):
        return bool(result)
    return False


def _timezone_designator(value: str) -> bool:
    if value.endswith("Z"):
        return True
    clock = value[10:]
    return "+" in clock or "-" in clock


def _series_kind(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(series):
        return "bool"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        timezone = getattr(series.dtype, "tz", None)
        return "datetime_tz" if timezone is not None else "datetime"
    values = [value for value in non_null.tolist() if not _missing(value)]
    if not values:
        return "empty"
    if all(isinstance(value, (pd.Timestamp, datetime)) for value in values):
        aware = [value.tzinfo is not None for value in values]
        if any(aware) and not all(aware):
            return "datetime_mixed_tz"
        return "datetime_tz" if any(aware) else "datetime"
    texts = [value if isinstance(value, str) else None for value in values]
    if all(isinstance(value, str) for value in texts) and all(
        _ISO_DATE.fullmatch(value) for value in texts
    ):
        return "iso_date"
    if all(isinstance(value, str) for value in texts) and all(
        _ISO_DATETIME.fullmatch(value) for value in texts
    ):
        if any(_timezone_designator(value) for value in texts):
            return "iso_datetime_tz"
        return "iso_datetime"
    return "string"


def _kinds_compatible(left_kind: str, right_kind: str, left_series, right_series) -> bool:
    if left_kind != right_kind:
        return False
    if left_kind in {"empty", "datetime_mixed_tz"}:
        return False
    if left_kind == "datetime_tz":
        return str(getattr(left_series.dtype, "tz", None)) == str(
            getattr(right_series.dtype, "tz", None)
        )
    return left_kind in {
        "number",
        "bool",
        "string",
        "iso_date",
        "iso_datetime",
        "iso_datetime_tz",
        "datetime",
    }


def _inferred_frequency(series: pd.Series, kind: str) -> str | None:
    if kind == "iso_date":
        parsed = pd.to_datetime(
            series.dropna().astype(str).str.strip(), format="%Y-%m-%d", errors="coerce"
        )
    elif kind == "iso_datetime":
        text = series.dropna().astype(str).str.strip().str.replace(" ", "T", n=1, regex=False)
        parsed = pd.to_datetime(text.str.slice(0, 19), format="%Y-%m-%dT%H:%M:%S", errors="coerce")
    elif kind in {"datetime", "datetime_tz"}:
        parsed = pd.to_datetime(series.dropna(), errors="coerce")
    else:
        return None
    if parsed.empty or bool(parsed.isna().any()):
        return None
    return infer_temporal_frequency(parsed)


def frequency_class(label: str | None) -> str | None:
    """Map a declared or estimated frequency label to one coarse class."""
    if not label:
        return None
    text = label.lower()
    if "not specified" in text:
        return None
    for name, tokens in _FREQUENCY_CLASSES:
        if any(token in text for token in tokens):
            return name
    return None


def _declared(frequencies, dataset_id: str) -> str | None:
    raw = (frequencies or {}).get(dataset_id)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _internal_frequency_conflict(declared: str | None, inferred: str | None) -> bool:
    declared_class = frequency_class(declared)
    inferred_class = frequency_class(inferred)
    return bool(declared_class and inferred_class and declared_class != inferred_class)


def _unit(units, dataset_id: str, column: str) -> str | None:
    raw = (units or {}).get(dataset_id, {}).get(column)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _same_name_unit_notes(left, right, units) -> list[str]:
    notes = []
    shared = [name for name in left.column_names if name in set(right.column_names)]
    for name in shared:
        left_unit = _unit(units, left.dataset_id, name)
        right_unit = _unit(units, right.dataset_id, name)
        if left_unit and right_unit and left_unit != right_unit:
            notes.append(
                f"Same-name field {name} is scoped to each dataset "
                f"({left_unit} vs {right_unit}) and was not converted."
            )
    return notes


def _normalize_join(join_type: Any) -> str | None:
    if not isinstance(join_type, str):
        return None
    normalized = join_type.strip().lower()
    if normalized in JOIN_TYPES:
        return normalized
    return None


def _estimated_rows(evidence: KeyEvidence, join_type: str) -> int:
    return {
        "inner": evidence.estimated_inner_rows,
        "left": evidence.estimated_left_rows,
        "right": evidence.estimated_right_rows,
        "outer": evidence.estimated_outer_rows,
    }[join_type]


def _duplicate_key_count(counts: dict) -> int:
    return sum(1 for count in counts.values() if count > 1)


def _rows_in_duplicate_keys(counts: dict) -> int:
    return sum(count for count in counts.values() if count > 1)


def _rate(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return part / whole


def _optional_rate(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return part / whole


def _frequency_cell(candidate: KeyEvidence) -> str:
    if not candidate.left_frequency and not candidate.right_frequency:
        return "—"
    left = candidate.left_frequency or "unknown"
    right = candidate.right_frequency or "unknown"
    if candidate.mixed_frequency:
        return f"mismatch: {left} vs {right}"
    return left if left == right else f"{left} vs {right}"


def _find_ref(bundle: DatasetBundle, dataset_id: str):
    if not isinstance(dataset_id, str):
        return None
    for ref in bundle.datasets:
        if ref.dataset_id == dataset_id:
            return ref
    return None


def _reject_unknown_ids(units, frequencies, known: set[str]) -> None:
    for label, mapping in (("column units", units), ("temporal frequencies", frequencies)):
        unknown = sorted(set(mapping) - known)
        if unknown:
            raise ValueError(f"Unknown dataset ID(s) in {label}: {', '.join(unknown)}.")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
