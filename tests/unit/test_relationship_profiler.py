"""Offline evidence and join-preview checks. No model and no saved dataset."""

import ast
from pathlib import Path

import pandas as pd
import pytest

from schemas.dataset_bundle import BUNDLE_LIMITATIONS
from schemas.relationships import MAX_JOIN_COLUMNS, MAX_JOIN_ROWS, MAX_PREVIEW_ROWS
from tools.dataset_bundle import build_dataset_bundle
from tools.relationship_profiler import (
    frequency_class,
    preview_join,
    profile_relationships,
    relationship_table_rows,
)

SALES = b"date,value\n2026-01-01,10\n2026-01-02,30\n2026-01-03,20\n2026-01-04,40\n"
WEATHER = b"date,value\n2026-01-01,100\n2026-01-02,80\n2026-01-03,90\n"
POPULATION = b"region,population\nNorth,100\nNorth,110\n,40\nSouth,50\n"
OUTCOMES = b"region,outcome\nNorth,1\nEast,3\n"
STATIONS = b"station_id,rainfall_mm\nA,1\nB,2\nC,3\nD,4\n"
DAILY = b"date,sales\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n2026-01-04,4\n"
MONTHLY = b"date,rain\n2026-01-01,10\n2026-02-01,11\n2026-03-01,12\n2026-04-01,13\n"


def _bundle(files: list[tuple[str, bytes]]):
    return build_dataset_bundle(files, project_id="mcm-c-demo")


def _snapshot(bundle):
    return {
        ref.dataset_id: (
            bundle.loaded_dataset(ref.dataset_id).frame.copy(deep=True),
            bundle.loaded_dataset(ref.dataset_id).raw_bytes,
        )
        for ref in bundle.datasets
    }


def _assert_unchanged(bundle, before) -> None:
    for dataset_id, (frame, raw) in before.items():
        loaded = bundle.loaded_dataset(dataset_id)
        pd.testing.assert_frame_equal(loaded.frame, frame)
        assert loaded.raw_bytes == raw
    assert bundle.manifest.joined is False
    assert bundle.manifest.limitations == list(BUNDLE_LIMITATIONS)


def _candidate(report, left_column: str, right_column: str | None = None):
    right_column = left_column if right_column is None else right_column
    matches = [
        candidate
        for pair in report.pairs
        for candidate in pair.candidates
        if candidate.left_column == left_column and candidate.right_column == right_column
    ]
    assert len(matches) == 1
    return matches[0]


def _ids(bundle) -> dict[str, str]:
    return {ref.file_name: ref.dataset_id for ref in bundle.datasets}


def test_profiler_does_not_import_or_call_a_model():
    source = Path("tools/relationship_profiler.py").read_text(encoding="utf-8")
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    assert not any(
        name == "agents" or name.startswith(("agents.", "llm.")) or name == "llm"
        for name in modules
    )
    assert ".merge(" not in source.split("def preview_join", 1)[0]


def test_sales_and_weather_dates_are_one_to_one_and_preview_is_explicit():
    bundle = _bundle([("sales.csv", SALES), ("weather.csv", WEATHER)])
    before = _snapshot(bundle)
    report = profile_relationships(bundle)
    _assert_unchanged(bundle, before)
    date_key = _candidate(report, "date")
    value_key = _candidate(report, "value")
    assert date_key.cardinality == "ONE_TO_ONE"
    assert date_key.overlap_key_count == 3
    assert date_key.left_unmatched_row_count == 1
    assert date_key.safe_to_preview is True
    assert date_key.mixed_frequency is False
    assert frequency_class(date_key.left_frequency) == "daily"
    assert frequency_class(date_key.right_frequency) == "daily"
    assert value_key.cardinality == "NO_OVERLAP"
    assert value_key.safe_to_preview is False
    assert report.pairs[0].verdict == "ONE_TO_ONE"
    assert report.joined is False
    assert report.persisted is False

    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["sales.csv"],
        right_dataset_id=ids["weather.csv"],
        left_key="date",
        right_key="date",
        join_type="inner",
    )
    _assert_unchanged(bundle, before)
    assert preview.status == "preview"
    assert preview.persisted is False
    assert preview.lineage is not None
    assert preview.lineage.aggregated is False
    assert preview.lineage.resampled is False
    assert preview.lineage.units_coerced is False
    assert preview.output_row_count == 3
    assert preview.unmatched_left_rows == 1
    value_columns = [column for column in preview.preview_columns if column.endswith(".value")]
    assert len(value_columns) == 2
    assert value_columns[0].startswith(ids["sales.csv"])
    assert value_columns[1].startswith(ids["weather.csv"])
    assert "value" not in preview.preview_columns
    first = preview.preview_rows[0]
    assert first[f"{ids['sales.csv']}.value"] == 10
    assert first[f"{ids['weather.csv']}.value"] == 100
    assert (
        "not saved" in " ".join(preview.warnings).lower() or "not saved" in preview.message.lower()
    )

    left_preview = preview_join(
        bundle,
        left_dataset_id=ids["sales.csv"],
        right_dataset_id=ids["weather.csv"],
        left_key="date",
        right_key="date",
        join_type="left",
    )
    assert left_preview.output_row_count == 4
    assert left_preview.unmatched_left_rows == 1
    _assert_unchanged(bundle, before)


def test_population_duplicates_and_unmatched_keys_are_reported_without_aggregation():
    bundle = _bundle([("population.csv", POPULATION), ("outcomes.csv", OUTCOMES)])
    before = _snapshot(bundle)
    report = profile_relationships(bundle)
    region = _candidate(report, "region")
    assert region.left_duplicate_key_count == 1
    assert region.left_rows_in_duplicate_keys == 2
    assert region.left_null_count == 1
    assert region.left_unmatched_row_count == 1
    assert region.right_unmatched_row_count == 1
    assert region.cardinality == "MANY_TO_ONE"
    assert region.overlap_key_count == 1
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["population.csv"],
        right_dataset_id=ids["outcomes.csv"],
        left_key="region",
        right_key="region",
        join_type="inner",
    )
    assert preview.status == "preview"
    assert preview.output_row_count == 2
    populations = [row[f"{ids['population.csv']}.population"] for row in preview.preview_rows]
    assert populations == [100, 110]
    assert {row[f"{ids['outcomes.csv']}.outcome"] for row in preview.preview_rows} == {1}
    assert any("not aggregated" in warning.lower() for warning in preview.warnings)
    assert preview.unmatched_right_rows == 1
    _assert_unchanged(bundle, before)


def test_unrelated_datasets_abstain():
    bundle = _bundle([("stations.csv", STATIONS), ("outcomes.csv", OUTCOMES)])
    before = _snapshot(bundle)
    report = profile_relationships(bundle)
    pair = report.pairs[0]
    assert pair.verdict == "UNRELATED"
    assert pair.state == "cannot safely join"
    assert pair.candidates == []
    assert pair.can_safely_join is False
    rows = relationship_table_rows(report)
    assert rows[0]["State"] == "cannot safely join"
    assert "cannot safely join" in rows[0]["Caveats"]
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["stations.csv"],
        right_dataset_id=ids["outcomes.csv"],
        left_key="station_id",
        right_key="region",
        join_type="outer",
    )
    assert preview.status == "blocked"
    assert preview.reason == "cannot_safely_join"
    assert preview.preview_rows == []
    assert "cannot safely join" in preview.message
    _assert_unchanged(bundle, before)


def test_mixed_frequencies_are_refused_without_alignment():
    bundle = _bundle([("daily.csv", DAILY), ("monthly.csv", MONTHLY)])
    before = _snapshot(bundle)
    report = profile_relationships(bundle)
    date_key = _candidate(report, "date")
    assert date_key.mixed_frequency is True
    assert frequency_class(date_key.left_frequency) == "daily"
    assert frequency_class(date_key.right_frequency) == "monthly"
    assert date_key.safe_to_preview is False
    assert report.pairs[0].verdict == "UNKNOWN"
    assert report.pairs[0].state == "cannot safely join"
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["daily.csv"],
        right_dataset_id=ids["monthly.csv"],
        left_key="date",
        right_key="date",
        join_type="inner",
    )
    assert preview.status == "blocked"
    assert preview.reason == "frequency_mismatch"
    assert preview.preview_rows == []
    assert preview.lineage is not None
    assert preview.lineage.resampled is False
    assert "not resampled" in preview.message
    assert "cannot safely join" in preview.message
    assert len(bundle.loaded_dataset(ids["daily.csv"]).frame) == 4
    _assert_unchanged(bundle, before)

    aligned = _bundle([("sales.csv", SALES), ("weather.csv", WEATHER)])
    aligned_ids = _ids(aligned)
    declared = profile_relationships(
        aligned,
        temporal_frequency_by_dataset={
            aligned_ids["sales.csv"]: "Daily",
            aligned_ids["weather.csv"]: "Monthly",
        },
    )
    assert _candidate(declared, "date").mixed_frequency is True
    blocked = preview_join(
        aligned,
        left_dataset_id=aligned_ids["sales.csv"],
        right_dataset_id=aligned_ids["weather.csv"],
        left_key="date",
        right_key="date",
        join_type="inner",
        temporal_frequency_by_dataset={
            aligned_ids["sales.csv"]: "Daily",
            aligned_ids["weather.csv"]: "Monthly",
        },
    )
    assert blocked.reason == "frequency_mismatch"


def test_same_name_fields_stay_scoped_when_units_differ():
    bundle = _bundle([("sales.csv", SALES), ("weather.csv", WEATHER)])
    ids = _ids(bundle)
    units = {
        ids["sales.csv"]: {"value": "kg"},
        ids["weather.csv"]: {"value": "lb"},
    }
    report = profile_relationships(bundle, column_units_by_dataset=units)
    assert any("kg" in caveat and "lb" in caveat for caveat in report.pairs[0].caveats)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["sales.csv"],
        right_dataset_id=ids["weather.csv"],
        left_key="date",
        right_key="date",
        join_type="inner",
        column_units_by_dataset=units,
    )
    assert preview.status == "preview"
    assert [column for column in preview.preview_columns if column.endswith(".value")] == [
        f"{ids['sales.csv']}.value",
        f"{ids['weather.csv']}.value",
    ]
    assert any("were not merged" in warning for warning in preview.warnings)
    assert any("kg" in warning and "lb" in warning for warning in preview.warnings)
    key_units = {
        ids["sales.csv"]: {"date": "calendar-day"},
        ids["weather.csv"]: {"date": "local-day"},
    }
    refused = preview_join(
        bundle,
        left_dataset_id=ids["sales.csv"],
        right_dataset_id=ids["weather.csv"],
        left_key="date",
        right_key="date",
        join_type="inner",
        column_units_by_dataset=key_units,
    )
    assert refused.status == "blocked"
    assert refused.reason == "unit_mismatch"
    assert refused.preview_rows == []


def test_many_to_many_is_rejected():
    bundle = _bundle(
        [
            ("left.csv", b"id,left_note\n1,a\n1,b\n"),
            ("right.csv", b"id,right_note\n1,c\n1,d\n"),
        ]
    )
    before = _snapshot(bundle)
    report = profile_relationships(bundle)
    assert _candidate(report, "id").cardinality == "MANY_TO_MANY"
    assert report.pairs[0].state == "cannot safely join"
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert preview.status == "blocked"
    assert preview.reason == "many_to_many"
    assert preview.preview_rows == []
    assert preview.output_row_count is None
    assert "cannot safely join" in preview.message
    assert "many-to-many" in preview.message
    _assert_unchanged(bundle, before)


def test_oversized_untrusted_and_invalid_joins_are_refused():
    count = MAX_JOIN_ROWS + 1
    left_rows = "\n".join(f"{index},{index}" for index in range(count))
    right_rows = "\n".join(f"{index},{index + 1}" for index in range(count))
    bundle = _bundle(
        [
            ("left.csv", f"id,left_amount\n{left_rows}\n".encode()),
            ("right.csv", f"id,right_amount\n{right_rows}\n".encode()),
        ]
    )
    before = _snapshot(bundle)
    ids = _ids(bundle)
    oversized = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert oversized.status == "blocked"
    assert oversized.reason == "oversized_result"
    assert oversized.preview_rows == []
    _assert_unchanged(bundle, before)

    wide_header = ["id", *[f"c{index}" for index in range(MAX_JOIN_COLUMNS)]]
    wide = (",".join(wide_header) + "\n" + ",".join(["1"] * len(wide_header)) + "\n").encode()
    wide_bundle = _bundle(
        [
            ("wide_left.csv", wide),
            ("wide_right.csv", wide.replace(b"c0", b"d0")),
        ]
    )
    wide_ids = _ids(wide_bundle)
    wide_result = preview_join(
        wide_bundle,
        left_dataset_id=wide_ids["wide_left.csv"],
        right_dataset_id=wide_ids["wide_right.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert wide_result.reason == "oversized_result"
    assert "column" in wide_result.message

    untrusted = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key=f"{ids['left.csv']}.id",
        right_key="id",
        join_type="inner",
    )
    assert untrusted.reason == "untrusted_key"
    missing = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="id == 1",
        right_key="id",
        join_type="left",
    )
    assert missing.reason == "untrusted_key"
    invalid = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="id",
        right_key="id",
        join_type="cross",
    )
    assert invalid.reason == "invalid_join_strategy"
    assert invalid.preview_rows == []
    unknown = preview_join(
        bundle,
        left_dataset_id="ds_missing_aaaaaaaaaaaa",
        right_dataset_id=ids["right.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert unknown.reason == "unknown_dataset"
    same = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["left.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert same.reason == "same_dataset"
    _assert_unchanged(bundle, before)


def test_two_overlapping_keys_stay_unknown_until_one_is_chosen():
    bundle = _bundle(
        [
            ("left.csv", b"id,code,left_value\n1,a,10\n2,b,20\n3,c,30\n"),
            ("right.csv", b"id,code,right_value\n1,a,100\n2,b,200\n3,c,300\n"),
        ]
    )
    report = profile_relationships(bundle)
    assert report.pairs[0].verdict == "UNKNOWN"
    assert report.pairs[0].state == "ambiguous"
    assert report.pairs[0].can_safely_join is False
    assert _candidate(report, "id").safe_to_preview is True
    assert _candidate(report, "code").safe_to_preview is True
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert preview.status == "preview"
    assert preview.lineage is not None
    assert preview.lineage.left_column == "id"
    assert preview.output_row_count == 3


def test_preview_truncates_display_without_refusing_a_bounded_result():
    count = MAX_PREVIEW_ROWS + 5
    rows = "\n".join(f"{index},{index}" for index in range(count))
    right_rows = "\n".join(f"{index},{index + 5}" for index in range(count))
    bundle = _bundle(
        [
            ("left.csv", f"id,left_amount\n{rows}\n".encode()),
            ("right.csv", f"id,right_amount\n{right_rows}\n".encode()),
        ]
    )
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="id",
        right_key="id",
        join_type="inner",
    )
    assert preview.status == "preview"
    assert preview.truncated is True
    assert preview.preview_row_count == MAX_PREVIEW_ROWS
    assert preview.output_row_count == count


def test_differently_named_iso_dates_are_candidates_and_ambiguous_dates_are_not_guessed():
    bundle = _bundle(
        [
            ("left.csv", b"start_date,amount\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n"),
            ("right.csv", b"obs_date,reading\n2026-01-01,9\n2026-01-02,8\n2026-01-03,7\n"),
        ]
    )
    report = profile_relationships(bundle)
    candidate = _candidate(report, "start_date", "obs_date")
    assert candidate.cardinality == "ONE_TO_ONE"
    assert candidate.safe_to_preview is True
    ambiguous = _bundle(
        [
            (
                "left.csv",
                b"start_date,end_date,amount\n"
                b"2026-01-01,2026-01-02,1\n2026-01-02,2026-01-03,2\n2026-01-03,2026-01-04,3\n",
            ),
            ("right.csv", b"obs_date,reading\n2026-01-01,9\n2026-01-02,8\n2026-01-03,7\n"),
        ]
    )
    ambiguous_report = profile_relationships(ambiguous)
    assert ambiguous_report.pairs[0].verdict == "UNKNOWN"
    assert ambiguous_report.pairs[0].candidates == []
    assert "No date pair was guessed" in " ".join(ambiguous_report.pairs[0].caveats)


def test_incompatible_types_are_not_coerced():
    bundle = _bundle(
        [
            ("left.csv", b"code,left_value\nA,1\nB,2\n"),
            ("right.csv", b"code,right_value\n1,1\n2,2\n"),
        ]
    )
    report = profile_relationships(bundle)
    assert _candidate(report, "code").dtype_compatible is False
    assert _candidate(report, "code").cardinality == "UNKNOWN"
    ids = _ids(bundle)
    preview = preview_join(
        bundle,
        left_dataset_id=ids["left.csv"],
        right_dataset_id=ids["right.csv"],
        left_key="code",
        right_key="code",
        join_type="inner",
    )
    assert preview.reason == "incompatible_dtype"
    assert "not coerced" in preview.message


def test_profile_relationships_requires_two_datasets():
    bundle = _bundle([("sales.csv", SALES)])
    with pytest.raises(ValueError, match="at least two"):
        profile_relationships(bundle)
