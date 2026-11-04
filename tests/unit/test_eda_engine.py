from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report
from tools.eda_artifacts import render_markdown_report

def test_eda_report_golden_stats_and_warnings():
    dataset = load_dataset(b"record_id,value,category\n1,10,A\n2,20,B\n3,,A\n3,,A\n", "demo.csv")
    report = build_eda_report(dataset, "project-1")
    assert report.dataset.row_count == 4
    assert report.dataset.column_count == 3
    assert report.dataset.duplicate_row_count == 1
    value = next(item for item in report.dataset.columns if item.name == "value")
    assert value.missing_count == 2
    assert value.numeric_summary["mean"] == 15.0
    assert value.outlier_count_iqr == 0
    assert report.numeric_correlations
    assert any("missing values" in item for item in report.warnings)
    assert any("duplicated rows" in item for item in report.warnings)

def test_markdown_report_has_traceability_and_caveats():
    dataset = load_dataset(b"x,y\n1,2\n2,4\n", "tiny.csv")
    report = build_eda_report(dataset, "demo")
    markdown = render_markdown_report(report)
    assert "SHA-256" in markdown
    assert "does not establish causation" in markdown


def test_date_column_is_inferred_and_trend_metadata_is_recorded():
    dataset = load_dataset(
        b"date,demand\n2026-01-01,10\n2026-01-02,12\n2026-01-03,15\n",
        "trend.csv",
    )
    report = build_eda_report(dataset, "demo")
    date_profile = next(item for item in report.dataset.columns if item.name == "date")
    assert date_profile.dtype == "datetime (inferred)"
    assert date_profile.datetime_min.startswith("2026-01-01")
    assert report.summary["datetime_columns"] == ["date"]


def test_artifacts_are_saved_with_hash_based_directory(tmp_path):
    from tools.eda_artifacts import save_eda_artifacts

    dataset = load_dataset(b"x,y\n1,2\n2,4\n3,6\n", "sample.csv")
    report = build_eda_report(dataset, "demo-project")
    artifacts = save_eda_artifacts(dataset, report, tmp_path)
    assert (tmp_path / "demo-project" / "eda" / dataset.sha256[:12] / "eda_report.json").exists()
    assert (tmp_path / "demo-project" / "eda" / dataset.sha256[:12] / "eda_report.md").exists()
    assert len(artifacts["chart_paths"]) == 2
    import json
    saved_report = json.loads((tmp_path / "demo-project" / "eda" / dataset.sha256[:12] / "eda_report.json").read_text(encoding="utf-8"))
    assert saved_report["chart_paths"] == artifacts["chart_paths"]
