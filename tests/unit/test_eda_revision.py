from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report
from tools.chart_catalog import fallback_chart_plan
from tools.chart_executor import execute_chart_plan
from tools.eda_artifacts import save_eda_artifacts


def test_dataset_context_captures_source_period_frequency_and_units():
    dataset = load_dataset(
        b"date,price\n2026-01-01,10\n2026-01-02,12\n2026-01-03,11\n",
        "prices.csv",
    )
    report = build_eda_report(
        dataset,
        "demo",
        data_source="Official sample dataset",
        temporal_frequency="Daily",
        column_units={"price": "USD / unit"},
    )

    assert report.dataset.data_source == "Official sample dataset"
    assert report.dataset.temporal_frequency == "Daily"
    assert report.dataset.period_start.startswith("2026-01-01")
    assert report.dataset.period_end.startswith("2026-01-03")
    assert "approximately daily" in report.dataset.inferred_frequency
    assert report.dataset.column_units == {"price": "USD / unit"}
    price_profile = next(item for item in report.dataset.columns if item.name == "price")
    assert price_profile.unit == "USD / unit"


def test_fallback_chart_plan_applies_user_provided_units():
    dataset = load_dataset(
        b"date,price\n2026-01-01,10\n2026-01-02,12\n2026-01-03,11\n",
        "prices.csv",
    )
    report = build_eda_report(dataset, "demo", column_units={"price": "USD / unit"})
    plan = fallback_chart_plan(report)

    histogram = next(chart for chart in plan.charts if chart.chart_type == "histogram")
    trend = next(chart for chart in plan.charts if chart.chart_type == "time_series")
    assert histogram.x_unit == "USD / unit"
    assert trend.y_unit == "USD / unit"
    assert "USD / unit" in trend.y_label


def test_chart_metrics_and_provenance_are_retained_in_report(tmp_path):
    dataset = load_dataset(
        b"date,price\n2026-01-01,10\n2026-01-02,12\n2026-01-03,11\n",
        "prices.csv",
    )
    report = build_eda_report(dataset, "demo", data_source="Official source")
    artifacts = save_eda_artifacts(dataset, report, tmp_path)

    assert len(artifacts["chart_metadata"]) == 2
    for chart in artifacts["chart_metadata"]:
        assert chart["source_sha256"] == dataset.sha256
        assert chart["source_columns"]
        assert chart["generated_at_utc"]
        assert chart["chart_spec_version"] == "1.0"

    trend = next(item for item in artifacts["chart_metadata"] if item["spec"]["chart_type"] == "time_series")
    assert trend["metrics"]["first"] == 10.0
    assert trend["metrics"]["last"] == 11.0
    assert trend["metrics"]["change_pct"] == 10.0


def test_markdown_report_exposes_data_context_and_figure_labels(tmp_path):
    dataset = load_dataset(
        b"date,price\n2026-01-01,10\n2026-01-02,12\n2026-01-03,11\n",
        "prices.csv",
    )
    report = build_eda_report(
        dataset, "demo", data_source="Official source",
        temporal_frequency="Daily", column_units={"price": "USD / unit"},
    )
    artifacts = save_eda_artifacts(dataset, report, tmp_path)
    markdown = open(artifacts["report_markdown_path"], encoding="utf-8").read()

    assert "Data source: Official source" in markdown
    assert "User-declared frequency: Daily" in markdown
    assert "USD / unit" in markdown
    assert "fig:distribution_1" in markdown
    assert "Source SHA-256" in markdown
    assert "Insight status" in markdown
