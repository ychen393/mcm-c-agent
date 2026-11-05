import io
import json
import re

import pandas as pd
import pytest

from schemas.dataset_bundle import BUNDLE_LIMITATIONS
from schemas.eda import EDAReport
from tools.data_loader import DEFAULT_MAX_FILE_SIZE, load_dataset
from tools.dataset_bundle import (
    ABSOLUTE_MAX_DATASETS,
    DEFAULT_MAX_BUNDLE_BYTES,
    build_bundle_profiles,
    build_dataset_bundle,
)
from tools.eda_engine import build_eda_report


def _body(report: EDAReport) -> dict:
    payload = report.model_dump(mode="json")
    payload.pop("generated_at_utc")
    payload["dataset"].pop("loaded_at_utc")
    return payload


def _xlsx(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


def test_single_file_preserves_loader_and_eda_report():
    raw = b"record_id,value,category\n1,10,A\n2,20,B\n3,,A\n3,,A\n"
    direct = load_dataset(raw, "demo.csv")
    direct_report = build_eda_report(direct, "project-1")
    bundle = build_dataset_bundle([("demo.csv", raw)], project_id="project-1")

    assert len(bundle.datasets) == 1
    ref = bundle.datasets[0]
    loaded = bundle.loaded_dataset(ref.dataset_id)
    assert loaded.sha256 == direct.sha256
    assert loaded.frame.equals(direct.frame)
    assert list(loaded.frame.columns) == ["record_id", "value", "category"]
    assert ref.file_name == ref.display_name == "demo.csv"
    assert ref.sha256 == direct.sha256
    assert bundle.manifest.joined is False
    assert bundle.manifest.limitations == list(BUNDLE_LIMITATIONS)

    profiles = build_bundle_profiles(bundle)
    assert list(profiles) == [ref.dataset_id]
    profile = profiles[ref.dataset_id]
    assert profile.project_id == "project-1"
    assert _body(profile.report) == _body(direct_report)
    manifest = json.dumps(bundle.manifest.model_dump())
    assert "raw_bytes" not in manifest
    assert "record_id,value,category" not in manifest


def test_two_csv_files_stay_independent():
    sales = b"region,amount\nEast,5\nWest,7\n"
    costs = b"region,amount\nEast,1\nWest,2\nNorth,3\n"
    bundle = build_dataset_bundle(
        [("sales.csv", sales), ("costs.csv", costs)],
        project_id="bundle-demo",
    )
    assert [ref.file_name for ref in bundle.datasets] == ["sales.csv", "costs.csv"]
    assert len({ref.dataset_id for ref in bundle.datasets}) == 2
    profiles = build_bundle_profiles(
        bundle,
        data_source_by_dataset={
            bundle.datasets[0].dataset_id: "sales ledger",
            bundle.datasets[1].dataset_id: "cost ledger",
        },
    )
    sales_report = profiles[bundle.datasets[0].dataset_id].report
    costs_report = profiles[bundle.datasets[1].dataset_id].report
    assert sales_report.dataset.row_count == 2
    assert costs_report.dataset.row_count == 3
    assert sales_report.dataset.sha256 != costs_report.dataset.sha256
    assert sales_report.project_id == costs_report.project_id == "bundle-demo"
    assert sales_report.dataset.data_source == "sales ledger"
    assert costs_report.dataset.data_source == "cost ledger"
    assert sales_report.summary["row_count"] + costs_report.summary["row_count"] == 5


def test_csv_and_xlsx_are_both_registered():
    csv_raw = b"id,value\n1,10\n"
    xlsx_raw = _xlsx(pd.DataFrame({"id": [2], "value": [30]}))
    bundle = build_dataset_bundle(
        [("table.csv", csv_raw), ("table.xlsx", xlsx_raw)],
        project_id="mixed",
    )
    extensions = [ref.file_extension for ref in bundle.datasets]
    assert extensions == [".csv", ".xlsx"]
    profiles = build_bundle_profiles(bundle)
    means = [
        profiles[ref.dataset_id].report.dataset.columns[1].numeric_summary["mean"]
        for ref in bundle.datasets
    ]
    assert means == [10.0, 30.0]


def test_same_column_names_are_qualified_and_frames_are_not_renamed():
    sales = b"date,value\n2026-01-01,10\n2026-01-02,10\n"
    weather = b"date,value\n2026-01-01,100\n2026-01-02,100\n"
    bundle = build_dataset_bundle(
        [("sales.csv", sales), ("weather.csv", weather)],
        project_id="overlap",
    )
    qualified = [name for ref in bundle.datasets for name in ref.qualified_column_names]
    assert len(qualified) == len(set(qualified)) == 4
    sales_value = bundle.datasets[0].qualified_column_names[1]
    weather_value = bundle.datasets[1].qualified_column_names[1]
    assert sales_value != weather_value
    for ref in bundle.datasets:
        assert list(bundle.loaded_dataset(ref.dataset_id).frame.columns) == ["date", "value"]
    profiles = build_bundle_profiles(bundle)
    sales_mean = next(
        column.numeric_summary["mean"]
        for column in profiles[bundle.datasets[0].dataset_id].report.dataset.columns
        if column.name == "value"
    )
    weather_mean = next(
        column.numeric_summary["mean"]
        for column in profiles[bundle.datasets[1].dataset_id].report.dataset.columns
        if column.name == "value"
    )
    assert sales_mean == 10.0
    assert weather_mean == 100.0
    context = profiles[bundle.datasets[0].dataset_id].model_context()
    assert context["qualified_columns"][1].endswith(".value")
    assert "100" not in json.dumps(context["columns"])


def test_same_file_name_with_different_bytes_is_disambiguated():
    first = b"id,value\n1,10\n"
    second = b"id,value\n1,99\n"
    bundle = build_dataset_bundle(
        [("data.csv", first), ("data.csv", second)],
        project_id="names",
    )
    refs = bundle.datasets
    assert refs[0].file_name == refs[1].file_name == "data.csv"
    assert refs[0].display_name != refs[1].display_name
    assert refs[0].dataset_id != refs[1].dataset_id
    assert refs[0].sha256 != refs[1].sha256
    assert refs[0].display_name.startswith("data.csv#")
    assert refs[1].display_name.startswith("data.csv#")


def test_identical_content_is_rejected():
    raw = b"id,value\n1,10\n"
    with pytest.raises(ValueError, match="Duplicate dataset content"):
        build_dataset_bundle([("one.csv", raw), ("two.csv", raw)], project_id="dupes")


def test_too_many_files_are_rejected_and_five_are_accepted():
    uploads = [(f"part-{index}.csv", f"id,value\n{index},{index}\n".encode()) for index in range(6)]
    with pytest.raises(ValueError, match="at most 5 files"):
        build_dataset_bundle(uploads, project_id="too-many")
    bundle = build_dataset_bundle(uploads[:5], project_id="five")
    assert len(bundle.datasets) == 5
    assert ABSOLUTE_MAX_DATASETS == 5


def test_aggregate_size_limit_is_independent_of_per_file_limit():
    assert DEFAULT_MAX_FILE_SIZE == 20 * 1024 * 1024
    assert DEFAULT_MAX_BUNDLE_BYTES == 50 * 1024 * 1024
    first = b"id,value\n1,10\n"
    second = b"id,value\n2,20\n"
    with pytest.raises(ValueError, match="aggregate limit"):
        build_dataset_bundle(
            [("first.csv", first), ("second.csv", second)],
            project_id="bulk",
            max_file_size=1000,
            max_aggregate_bytes=len(first) + 1,
        )
    with pytest.raises(ValueError, match="upload limit"):
        build_dataset_bundle(
            [("large.csv", b"a" * 11)],
            project_id="bulk",
            max_file_size=10,
            max_aggregate_bytes=100,
        )


def test_invalid_file_names_the_failing_upload():
    with pytest.raises(ValueError, match="bad.csv"):
        build_dataset_bundle(
            [("ok.csv", b"id,value\n1,10\n"), ("bad.csv", b"\xff")],
            project_id="invalid",
        )
    with pytest.raises(ValueError, match="at least one file"):
        build_dataset_bundle([], project_id="empty")


def test_fingerprint_is_deterministic_and_order_sensitive():
    sales = b"region,amount\nEast,5\n"
    weather = b"day,temp\n2026-01-01,3\n"
    forward = build_dataset_bundle(
        [("sales.csv", sales), ("weather.csv", weather)],
        project_id="order",
    )
    reverse = build_dataset_bundle(
        [("weather.csv", weather), ("sales.csv", sales)],
        project_id="order",
    )
    again = build_dataset_bundle(
        [("sales.csv", sales), ("weather.csv", weather)],
        project_id="order",
    )
    assert forward.fingerprint == again.fingerprint
    assert forward.fingerprint != reverse.fingerprint
    assert {ref.sha256: ref.dataset_id for ref in forward.datasets} == {
        ref.sha256: ref.dataset_id for ref in reverse.datasets
    }
    assert [ref.position for ref in forward.datasets] == [0, 1]
    assert [ref.file_name for ref in reverse.datasets] == ["weather.csv", "sales.csv"]


def test_profile_context_omits_the_frame_and_unsampled_rows():
    labels = [f"cat-{index:02d}" for index in range(1, 13)] + ["zzz-late-token"]
    lines = ["id,label"] + [f"{index},{label}" for index, label in enumerate(labels, start=1)]
    raw = ("\n".join(lines) + "\n").encode()
    bundle = build_dataset_bundle([("wide.csv", raw)], project_id="profile")
    profile = build_bundle_profiles(bundle)[bundle.datasets[0].dataset_id]
    report_json = json.dumps(profile.report.model_dump(mode="json"))
    encoded = json.dumps(profile.model_context())
    assert "cat-01" in report_json
    assert "zzz-late-token" not in report_json
    assert "zzz-late-token" not in encoded
    assert raw.decode() not in report_json
    assert "frame" not in profile.model_dump()
    assert "raw_bytes" not in encoded
    assert all("sample_values" not in column for column in profile.model_context()["columns"])


def test_unknown_dataset_metadata_is_rejected():
    bundle = build_dataset_bundle([("only.csv", b"id,value\n1,2\n")], project_id="meta")
    with pytest.raises(ValueError, match="Unknown dataset ID"):
        build_bundle_profiles(bundle, data_source_by_dataset={"ds_missing_deadbeefdead": "nope"})


@pytest.mark.parametrize("file_name", ["黄金价格.csv", "USD指数.csv", "échantillon.csv", "🔍研究.csv"])
def test_unicode_file_names_keep_display_but_use_ascii_dataset_ids(file_name):
    raw = b"date,value\n2026-01-01,10\n2026-01-02,11\n"
    first = build_dataset_bundle([(file_name, raw)], project_id="unicode")
    again = build_dataset_bundle([(file_name, raw)], project_id="unicode")
    ref = first.datasets[0]
    assert ref.file_name == ref.display_name == file_name
    assert re.fullmatch(r"ds_[a-z0-9-]+_[0-9a-f]{12}(?:_[0-9]+)?", ref.dataset_id)
    assert ref.dataset_id == again.datasets[0].dataset_id
    assert first.fingerprint == again.fingerprint
    assert build_bundle_profiles(first)[ref.dataset_id].report.dataset.row_count == 2


def test_windows_upload_path_is_stripped_before_storing_provenance():
    raw = b"id,value\n1,2\n"
    bundle = build_dataset_bundle(
        [(r"C:\\Users\\student\\data\\黄金价格.csv", raw)], project_id="paths"
    )
    ref = bundle.datasets[0]
    assert ref.file_name == "黄金价格.csv"
    assert ref.display_name == "黄金价格.csv"
    assert "Users" not in json.dumps(bundle.manifest.model_dump())
    assert "\\\\" not in ref.file_name


class _ReadSpy(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        assert 0 < size <= 100
        return super().read(size)


def test_stream_input_is_bounded_by_per_file_size_before_materialization():
    stream = _ReadSpy(b"col,value\n" + b"1,2\n" * 20)
    with pytest.raises(ValueError, match="upload limit"):
        build_dataset_bundle(
            [("data.csv", stream)], project_id="bounded", max_file_size=15
        )
    assert stream.read_sizes and all(0 < n <= 16 for n in stream.read_sizes)
    assert stream.tell() <= 16


def test_stream_input_is_bounded_by_remaining_aggregate_size():
    first = b"id,value\n1,2\n"
    stream = _ReadSpy(b"id,value\n2,3\n")
    with pytest.raises(ValueError, match="aggregate limit"):
        build_dataset_bundle(
            [("first.csv", first), ("second.csv", stream)],
            project_id="bounded",
            max_file_size=100,
            max_aggregate_bytes=len(first) + 3,
        )
    assert stream.read_sizes and all(0 < n <= 4 for n in stream.read_sizes)
    assert stream.tell() <= 4


def test_upload_generator_is_capped_without_consuming_unbounded_input():
    def uploads():
        for index in range(1000):
            yield (f"{index}.csv", f"id,value\n{index},2\n".encode())

    with pytest.raises(ValueError, match="at most 5 files"):
        build_dataset_bundle(uploads(), project_id="bounded")
