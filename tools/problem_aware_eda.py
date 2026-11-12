"""Deterministic problem-aware EDA planning (Phase 3).

Consumes a ProblemSpecification (when present), an in-memory DatasetBundle, and
optional relationship evidence. Never invents joins, never merges frames, and
never requires a live LLM.
"""

from __future__ import annotations

from typing import Any

from schemas.eda_plan import (
    ConstraintReminder,
    DatasetMatchItem,
    FocusColumn,
    ProblemAwareEDAPlan,
    SuggestedRelationship,
)
from schemas.problem_specification import ProblemSpecification
from schemas.relationships import RelationshipReport
from tools.dataset_bundle import DatasetBundle

_PAST_DATA_IDS = frozenset({"c_past_data_only", "c_only_supplied_data"})
_GENERIC_MUST_NOT = (
    "Do not concatenate unrelated datasets.",
    "Do not invent join keys from similar column names alone.",
    "Do not merge until the user confirms an explicit preview.",
    "Do not resample, impute, forward-fill, or coerce units during EDA.",
)


def build_problem_aware_eda_plan(
    *,
    bundle: DatasetBundle,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    relationship_report: RelationshipReport | dict[str, Any] | None = None,
) -> ProblemAwareEDAPlan:
    """Build a CI-safe EDA plan. Empty/missing specs still yield safe guidance."""
    spec = _coerce_spec(problem_specification)
    relationships = _coerce_relationships(relationship_report)

    matches = _match_datasets(bundle, spec)
    reminders = _constraint_reminders(spec)
    focus = _focus_columns(bundle, spec)
    suggestions = _relationship_suggestions(bundle, relationships, spec)
    notes = _analysis_notes(spec, matches, reminders)
    must_not = list(_GENERIC_MUST_NOT)
    if spec is not None and any(item.id in _PAST_DATA_IDS for item in spec.constraints):
        must_not.append(
            "Do not use future prices or external series beyond the supplied past stream."
        )
    if any(item.stance == "cannot_join" for item in suggestions):
        must_not.append(
            "Do not force a join when relationship evidence is unjustified — "
            "keep datasets side by side."
        )

    return ProblemAwareEDAPlan(
        problem_id=spec.problem_id if spec else None,
        title=spec.title if spec else None,
        has_problem_specification=spec is not None,
        dataset_matches=matches,
        constraint_reminders=reminders,
        focus_by_dataset=focus,
        suggested_relationships=suggestions,
        must_not=must_not,
        analysis_notes=notes,
    )


def _coerce_spec(
    value: ProblemSpecification | dict[str, Any] | None,
) -> ProblemSpecification | None:
    if value is None:
        return None
    if isinstance(value, ProblemSpecification):
        return value
    if isinstance(value, dict):
        if not value:
            return None
        return ProblemSpecification.model_validate(value)
    raise TypeError("problem_specification must be a ProblemSpecification, mapping, or None.")


def _coerce_relationships(
    value: RelationshipReport | dict[str, Any] | None,
) -> RelationshipReport | None:
    if value is None:
        return None
    if isinstance(value, RelationshipReport):
        return value
    if isinstance(value, dict):
        if not value:
            return None
        return RelationshipReport.model_validate(value)
    raise TypeError("relationship_report must be a RelationshipReport, mapping, or None.")


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("\\", "/").split("/")[-1]


def _match_datasets(
    bundle: DatasetBundle, spec: ProblemSpecification | None
) -> list[DatasetMatchItem]:
    uploads = list(bundle.datasets)
    if spec is None or not spec.supplied_datasets:
        return [
            DatasetMatchItem(
                dataset_id=ref.dataset_id,
                upload_file_name=ref.file_name,
                expected_file_name=None,
                status="unmatched",
                notes="No supplied_datasets in ProblemSpecification; profile independently.",
            )
            for ref in uploads
        ]

    expected = {_normalize_name(item.file_name): item for item in spec.supplied_datasets}
    used: set[str] = set()
    matches: list[DatasetMatchItem] = []
    for ref in uploads:
        key = _normalize_name(ref.file_name)
        expected_item = expected.get(key)
        if expected_item is None:
            matches.append(
                DatasetMatchItem(
                    dataset_id=ref.dataset_id,
                    upload_file_name=ref.file_name,
                    expected_file_name=None,
                    status="unexpected_upload",
                    notes=(
                        "Uploaded file is not listed in ProblemSpecification.supplied_datasets. "
                        "Do not invent a role or join for it."
                    ),
                )
            )
            continue
        used.add(key)
        matches.append(
            DatasetMatchItem(
                dataset_id=ref.dataset_id,
                upload_file_name=ref.file_name,
                expected_file_name=expected_item.file_name,
                status="matched",
                notes=expected_item.statement,
            )
        )
    for key, item in expected.items():
        if key in used:
            continue
        matches.append(
            DatasetMatchItem(
                dataset_id=None,
                upload_file_name=None,
                expected_file_name=item.file_name,
                status="missing_upload",
                notes="Expected by the problem statement but not present in the current upload.",
            )
        )
    return matches


def _constraint_reminders(spec: ProblemSpecification | None) -> list[ConstraintReminder]:
    if spec is None:
        return []
    reminders: list[ConstraintReminder] = []
    for item in spec.constraints:
        implication = _eda_implication(item.id, item.constraint_kind, item.statement)
        if implication is None:
            continue
        reminders.append(
            ConstraintReminder(
                constraint_id=item.id,
                statement=item.statement,
                constraint_kind=item.constraint_kind,
                provenance=item.provenance,
                eda_implication=implication,
            )
        )
    return reminders


def _eda_implication(constraint_id: str, kind: str, statement: str) -> str | None:
    if constraint_id == "c_past_data_only" or kind == "information":
        return (
            "EDA and later models may only use information available on or before each "
            "decision date (no look-ahead)."
        )
    if constraint_id == "c_only_supplied_data" or kind == "data_use":
        return "Restrict analysis to the uploaded supplied CSVs; do not silently add external series."
    if kind == "assets":
        return "Keep gold and bitcoin profiles separate until a user-confirmed date alignment preview."
    if kind == "trading_calendar":
        return "Preserve each series' native calendar; do not silently fill missing trading days."
    if kind in {"capital", "transaction_cost"}:
        return f"Record for modeling context (not a join key): {statement[:240]}"
    if kind == "deliverable":
        return None
    return f"Respect during EDA planning: {statement[:240]}"


def _focus_columns(
    bundle: DatasetBundle, spec: ProblemSpecification | None
) -> list[FocusColumn]:
    expected_columns: dict[str, list[str]] = {}
    if spec is not None:
        for item in spec.supplied_datasets:
            expected_columns[_normalize_name(item.file_name)] = list(item.columns)

    focus: list[FocusColumn] = []
    for ref in bundle.datasets:
        notes: list[str] = [
            "Profile this file independently; qualified columns disambiguate overlaps."
        ]
        wanted = expected_columns.get(_normalize_name(ref.file_name), [])
        present = set(ref.column_names)
        for column in wanted:
            if column in present:
                notes.append(f"Problem-supplied column present: {column}")
            else:
                notes.append(f"Expected column '{column}' not found in upload.")
        if spec is not None and spec.problem_id == "2022_mcm_c":
            notes.append("Emphasize Date and price columns for past-only trading decisions.")
        focus.append(
            FocusColumn(
                dataset_id=ref.dataset_id,
                display_name=ref.display_name,
                file_name=ref.file_name,
                qualified_columns=list(ref.qualified_column_names),
                focus_notes=notes,
            )
        )
    return focus


def _relationship_suggestions(
    bundle: DatasetBundle,
    relationships: RelationshipReport | None,
    spec: ProblemSpecification | None,
) -> list[SuggestedRelationship]:
    if len(bundle.datasets) < 2:
        return []
    if relationships is None:
        return [
            SuggestedRelationship(
                left_dataset_id=bundle.datasets[0].dataset_id,
                right_dataset_id=bundle.datasets[1].dataset_id,
                left_display_name=bundle.datasets[0].display_name,
                right_display_name=bundle.datasets[1].display_name,
                stance="abstain",
                evidence_summary=(
                    "No relationship evidence was supplied. Run the relationship profiler "
                    "before considering any join preview."
                ),
                caveats=["No automatic join is proposed."],
            )
        ]

    suggestions: list[SuggestedRelationship] = []
    for pair in relationships.pairs:
        if pair.state == "cannot safely join" or pair.verdict in {"UNRELATED", "NO_OVERLAP"}:
            stance = "cannot_join"
            summary = (
                f"Evidence verdict={pair.verdict}; state={pair.state}. "
                "Do not invent a join — compare side by side."
            )
            left_col = right_col = None
        elif pair.can_safely_join and pair.candidates:
            best = next((c for c in pair.candidates if c.safe_to_preview), pair.candidates[0])
            stance = "suggest_preview"
            left_col, right_col = best.left_column, best.right_column
            summary = (
                f"Evidence supports a preview on {best.left_qualified_column} = "
                f"{best.right_qualified_column} (cardinality={best.cardinality}, "
                f"overlap_keys={best.overlap_key_count}). User confirmation required."
            )
        else:
            stance = "abstain"
            summary = (
                f"Relationship is {pair.verdict}/{pair.state}. "
                "Choose keys manually if justified; nothing is joined automatically."
            )
            left_col = right_col = None
            if pair.candidates:
                left_col = pair.candidates[0].left_column
                right_col = pair.candidates[0].right_column

        caveats = list(pair.caveats)
        if spec is not None and spec.problem_id == "2022_mcm_c":
            caveats.append(
                "2022 C gold and bitcoin share calendar dates only as a candidate key; "
                "gold market-day gaps must remain visible."
            )
        suggestions.append(
            SuggestedRelationship(
                left_dataset_id=pair.left_dataset_id,
                right_dataset_id=pair.right_dataset_id,
                left_display_name=pair.left_display_name,
                right_display_name=pair.right_display_name,
                left_column=left_col,
                right_column=right_col,
                stance=stance if stance != "cannot_join" else "cannot_join",
                evidence_summary=summary,
                caveats=caveats,
            )
        )
    return suggestions


def _analysis_notes(
    spec: ProblemSpecification | None,
    matches: list[DatasetMatchItem],
    reminders: list[ConstraintReminder],
) -> list[str]:
    notes = [
        "Independent per-dataset profiles remain the default EDA path.",
        "Cross-dataset integration requires an explicit user preview confirmation.",
    ]
    if spec is None:
        notes.append("No ProblemSpecification available; EDA proceeds without problem constraints.")
        return notes
    notes.append(f"ProblemSpecification problem_id={spec.problem_id} conditions this plan.")
    if any(item.status == "missing_upload" for item in matches):
        notes.append("One or more expected datasets are missing from the upload.")
    if any(item.status == "unexpected_upload" for item in matches):
        notes.append("Unexpected uploads are profiled independently and are not auto-joined.")
    if any(item.constraint_id in _PAST_DATA_IDS for item in reminders):
        notes.append("Past-data / supplied-data constraints are active for EDA planning.")
    if spec.problem_id == "2022_mcm_c":
        notes.append(
            "2022 MCM C: expect LBMA-GOLD.csv and BCHAIN-MKPRU.csv; keep series separate "
            "until a confirmed date-key preview."
        )
    return notes
