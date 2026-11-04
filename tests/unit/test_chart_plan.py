import pandas as pd
import pytest
from pydantic import ValidationError
from schemas.chart_plan import ChartPlan, ChartSpec
from tools.chart_plan_validator import validate_chart_plan
from tools.chart_executor import execute_chart_plan
from tools.chart_catalog import fallback_chart_plan
from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report


def spec(chart_id="chart_1", chart_type="histogram", x="value", y=None):
    return ChartSpec(
        chart_id=chart_id, chart_type=chart_type, title="Value overview",
        figure_label=f"fig:{chart_id}", x=x, y=y,
        x_label="Value", y_label="Frequency (count)",
        caption="Distribution of observed values in the dataset.",
        analytical_question="How are the observed values distributed?",
        rationale="Inspect spread before selecting the model.",
    )


def test_schema_rejects_missing_required_chart_labels():
    with pytest.raises(ValidationError):
        ChartSpec(chart_id="bad", chart_type="histogram", title="Example",
                  figure_label="fig:bad", x="value", x_label="", y_label="Count",
                  caption="Distribution for value field.",
                  analytical_question="What is the distribution?",
                  rationale="Understand data spread.")


def test_validator_rejects_missing_columns_and_duplicate_labels():
    df = pd.DataFrame({"value": [1, 2, 3]})
    with pytest.raises(ValueError, match="Unknown column"):
        validate_chart_plan(ChartPlan(charts=[spec(x="unknown")]), df)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_chart_plan(ChartPlan(charts=[spec(), spec(chart_id="chart_1")]), df)


def test_validator_rejects_nonnumeric_scatter_axis():
    df = pd.DataFrame({"name": ["a", "b"], "value": [2, 3]})
    with pytest.raises(ValueError, match="Numeric column required"):
        validate_chart_plan(ChartPlan(charts=[spec(chart_type="scatter", x="name", y="value")]), df)


def test_chart_executor_persists_labeled_png_and_metrics(tmp_path):
    df = pd.DataFrame({"value": [1, 2, 3, 4]})
    results = execute_chart_plan(ChartPlan(charts=[spec()]), df, tmp_path, "abc123")
    assert len(results) == 1
    assert results[0].chart_id == "chart_1"
    assert results[0].figure_label == "fig:chart_1"
    assert results[0].spec.caption
    assert results[0].metrics["median"] == 2.5
    assert results[0].source_sha256 == "abc123"
    assert (tmp_path / "chart_1.png").is_file()


def test_fallback_plan_remains_compatible_with_existing_two_histograms():
    dataset = load_dataset(b"x,y\n1,2\n2,4\n3,6\n", "sample.csv")
    report = build_eda_report(dataset, "demo")
    plan = fallback_chart_plan(report)
    assert plan.strategy == "deterministic"
    assert [chart.chart_type for chart in plan.charts] == ["histogram", "histogram"]
    validate_chart_plan(plan, dataset.frame)


def test_time_series_metadata_from_actual_values(tmp_path):
    df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                       "value": [10, 12, 11]})
    plan = ChartPlan(charts=[spec(chart_type="time_series", x="date", y="value")])
    result = execute_chart_plan(plan, df, tmp_path, "hash")[0]
    assert result.plotted_rows == 3
    assert result.metrics["first"] == 10
    assert result.metrics["last"] == 11
