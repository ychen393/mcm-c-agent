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
