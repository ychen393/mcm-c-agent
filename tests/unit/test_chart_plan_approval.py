import pytest

from schemas.chart_plan import ChartPlan
from tools.chart_catalog import fallback_chart_plan
from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report
from tools.eda_artifacts import save_eda_artifacts


def test_explicit_chart_plan_requires_human_approval(tmp_path):
    dataset = load_dataset(
        b"value\n1\n2\n3\n4\n",
        "values.csv",
    )
    report = build_eda_report(dataset, "approval-demo")
    plan = fallback_chart_plan(report)

    with pytest.raises(PermissionError, match="explicit human approval"):
        save_eda_artifacts(dataset, report, tmp_path, chart_plan=plan)


def test_approved_chart_plan_is_persisted_with_approval_provenance(tmp_path):
    dataset = load_dataset(
        b"value\n1\n2\n3\n4\n",
        "values.csv",
    )
    report = build_eda_report(dataset, "approval-demo")
    plan = fallback_chart_plan(report)

    artifacts = save_eda_artifacts(
        dataset,
        report,
        tmp_path,
        chart_plan=plan,
        human_approved=True,
    )

    assert artifacts["chart_paths"]
    assert report.summary["chart_plan_approval"]["status"] == "approved"
    assert report.chart_plan["strategy"] == "deterministic"
