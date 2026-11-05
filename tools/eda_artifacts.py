from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from schemas.chart_plan import ChartPlan
from schemas.eda import EDAReport
from tools.data_loader import LoadedDataset, safe_project_id


def _safe_stem(file_name: str) -> str:
    stem = Path(file_name).stem
    return re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-_")[:60] or "dataset"


def save_eda_artifacts(
    dataset: LoadedDataset,
    report: EDAReport,
    output_root: Path,
    *,
    chart_plan: ChartPlan | None = None,
    human_approved: bool = False,
) -> dict[str, str | list[str]]:
    if chart_plan is not None and not human_approved:
        raise PermissionError("Chart plan execution requires explicit human approval.")

    project_dir = output_root / safe_project_id(report.project_id) / "eda" / dataset.sha256[:12]
    project_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = project_dir / f"{_safe_stem(dataset.file_name)}{dataset.file_extension}"
    report_path = project_dir / "eda_report.json"
    markdown_path = project_dir / "eda_report.md"

    temp_dataset = dataset_path.with_suffix(dataset_path.suffix + ".tmp")
    temp_dataset.write_bytes(dataset.raw_bytes)
    os.replace(temp_dataset, dataset_path)

    # Legacy callers retain deterministic Phase A behavior. Any explicitly supplied
    # plan must pass through the human approval gate before chart execution.
    from tools.chart_catalog import fallback_chart_plan
    from tools.chart_executor import execute_chart_plan
    from tools.chart_plan_validator import validate_chart_plan

    plan = chart_plan or fallback_chart_plan(report)
    validate_chart_plan(plan, dataset.frame, report)
    if chart_plan is not None:
        report.summary["chart_plan_approval"] = {
            "status": "approved",
            "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    chart_results = execute_chart_plan(plan, dataset.frame, project_dir, dataset.sha256)
    chart_paths = [item.path for item in chart_results]
    report.chart_metadata = [item.model_dump(mode="json") for item in chart_results]
    report.chart_plan = plan.model_dump(mode="json")

    report.chart_paths = chart_paths
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return {
        "dataset_path": str(dataset_path),
        "report_json_path": str(report_path),
        "report_markdown_path": str(markdown_path),
        "chart_paths": chart_paths,
        "chart_metadata": report.chart_metadata,
    }


def render_markdown_report(report: EDAReport) -> str:
    data = report.dataset
    lines = [
        "# Exploratory Data Analysis Report",
        "",
        f"- Project: {report.project_id}",
        f"- Dataset: {data.file_name}",
        f"- SHA-256: {data.sha256}",
        f"- Shape: {data.row_count:,} rows × {data.column_count} columns",
        f"- Duplicate rows: {data.duplicate_row_count}",
        f"- Data source: {data.data_source or 'Not provided'}",
        f"- User-declared frequency: {data.temporal_frequency or 'Not provided'}",
        f"- Estimated frequency: {data.inferred_frequency or 'Not available'}",
        f"- Date period: {data.period_start or 'N/A'} to {data.period_end or 'N/A'}",
        f"- Chart planning strategy: {report.chart_plan.get('strategy', 'not recorded')}",
        f"- Planner: {report.chart_plan.get('planner_provider') or 'N/A'} / {report.chart_plan.get('planner_model') or 'N/A'}",
        f"- Chart-plan approval: {report.summary.get('chart_plan_approval', {}).get('status', 'not recorded')}",
        "",
        "## Column units",
        "",
        *([f"- {name}: {unit}" for name, unit in data.column_units.items()] or ["- Units not provided."]),
        "",
        "## Column profile",
        "",
        "| Column | Type | Unit | Missing | Unique | Numeric summary / Top values |",
        "|---|---|---|---:|---:|---|",
    ]
    for column in data.columns:
        if column.numeric_summary is not None:
            summary = column.numeric_summary
            detail = f"mean={summary['mean']}, median={summary['median']}, min={summary['min']}, max={summary['max']}"
        else:
            detail = ", ".join(
                f"{item['value']} ({item['count']})" for item in (column.top_values or [])[:5]
            )
        detail = detail.replace("|", "\\\\|")
        lines.append(
            f"| {column.name} | {column.dtype} | {column.unit or 'Not provided'} | {column.missing_count} "
            f"({column.missing_rate:.1%}) | {column.unique_count} | {detail} |"
        )

    lines.extend(["", "## Data quality warnings", ""])
    if report.warnings:
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append("- No missingness, duplicate-row, or IQR outlier flags were detected.")

    lines.extend(["", "## Numeric correlations", ""])
    if report.numeric_correlations:
        for column, values in report.numeric_correlations.items():
            pairs = ", ".join(
                f"{name}: {value:.3f}" if value is not None else f"{name}: N/A"
                for name, value in values.items()
            )
            lines.append(f"- **{column}:** {pairs}")
    else:
        lines.append("- Fewer than two numeric columns; correlation matrix not generated.")

    lines.extend(["", "## Generated charts", ""])
    if report.chart_metadata:
        for item in report.chart_metadata:
            spec = item["spec"]
            lines.extend([
                f"### Rank {spec['rank']} · {spec['figure_label']} — {spec['title']}",
                f"**Relevance score:** {spec['relevance_score']:.0%} · **Analytical role:** {spec['analytical_role']}",
                f"![{spec['title']}]({Path(item['path']).name})",
                f"**Analytical question:** {spec['analytical_question']}",
                f"**Caption:** {spec['caption']}",
                f"**Axes:** {spec['x_label']} / {spec['y_label']}",
                f"**Source columns:** {', '.join(item.get('source_columns', [spec['x']] + ([spec['y']] if spec.get('y') else [])))}",
                f"**Plotted rows:** {item['plotted_rows']}",
                f"**Source SHA-256:** {item['source_sha256']}",
                f"**Computed metrics:** {item['metrics']}",
                "**Insight status:** Not generated; evidence-grounded interpretation is scheduled for Phase C.",
                "",
            ])
    else:
        lines.append("- No charts generated for this dataset.")

    lines.extend([
        "",
        "> Correlation is descriptive and does not establish causation. IQR flags are prompts for inspection, not automatic deletion rules.",
        "",
    ])
    return "\n".join(lines)
