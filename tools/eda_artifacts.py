from __future__ import annotations
import json
import os
import re
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from schemas.eda import EDAReport
from tools.data_loader import LoadedDataset, safe_project_id

def _safe_stem(file_name: str) -> str:
    stem = Path(file_name).stem
    return re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-_")[:60] or "dataset"

def save_eda_artifacts(dataset: LoadedDataset, report: EDAReport, output_root: Path) -> dict[str, str | list[str]]:
    project_dir = output_root / safe_project_id(report.project_id) / "eda" / dataset.sha256[:12]
    project_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = project_dir / f"{_safe_stem(dataset.file_name)}{dataset.file_extension}"
    report_path, markdown_path = project_dir / "eda_report.json", project_dir / "eda_report.md"
    temp_dataset = dataset_path.with_suffix(dataset_path.suffix + ".tmp")
    temp_dataset.write_bytes(dataset.raw_bytes)
    os.replace(temp_dataset, dataset_path)
    report_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    chart_paths: list[str] = []
    for column in dataset.frame.select_dtypes(include=["number"]).columns.tolist()[:6]:
        values = pd.to_numeric(dataset.frame[column], errors="coerce").dropna()
        if values.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(values, bins=min(30, max(5, int(len(values) ** 0.5))))
        ax.set(title=f"Distribution: {column}", xlabel=str(column), ylabel="Count")
        fig.tight_layout()
        chart_path = project_dir / f"distribution_{_safe_stem(str(column))}.png"
        fig.savefig(chart_path, dpi=130)
        plt.close(fig)
        chart_paths.append(str(chart_path))

    date_columns = [
        item.name for item in report.dataset.columns if item.datetime_min is not None
    ]
    trend_count = 0
    for date_column in date_columns:
        dates = pd.to_datetime(dataset.frame[date_column], errors="coerce")
        for value_column in numeric_columns:
            paired = pd.DataFrame({"date": dates, "value": pd.to_numeric(dataset.frame[value_column], errors="coerce")}).dropna()
            if len(paired) < 3:
                continue
            paired = paired.sort_values("date")
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(paired["date"], paired["value"], marker="o", linewidth=1.5)
            ax.set(title=f"Trend: {value_column} over {date_column}", xlabel=date_column, ylabel=value_column)
            fig.autofmt_xdate()
            fig.tight_layout()
            chart_path = project_dir / f"trend_{_safe_stem(str(value_column))}_by_{_safe_stem(date_column)}.png"
            fig.savefig(chart_path, dpi=130)
            plt.close(fig)
            chart_paths.append(str(chart_path))
            trend_count += 1
            if trend_count >= 3:
                break
        if trend_count >= 3:
            break

    return {"dataset_path": str(dataset_path), "report_json_path": str(report_path),
            "report_markdown_path": str(markdown_path), "chart_paths": chart_paths}

def render_markdown_report(report: EDAReport) -> str:
    data = report.dataset
    lines = ["# Exploratory Data Analysis Report", "", f"- Project: {report.project_id}",
        f"- Dataset: {data.file_name}", f"- SHA-256: {data.sha256}",
        f"- Shape: {data.row_count:,} rows × {data.column_count} columns",
        f"- Duplicate rows: {data.duplicate_row_count}", "", "## Column profile", "",
        "| Column | Type | Missing | Unique | Numeric summary / Top values |",
        "|---|---|---:|---:|---|"]
    for column in data.columns:
        if column.numeric_summary is not None:
            s = column.numeric_summary
            detail = f"mean={s['mean']}, median={s['median']}, min={s['min']}, max={s['max']}"
        else:
            detail = ", ".join(f"{x['value']} ({x['count']})" for x in (column.top_values or [])[:5])
        detail = detail.replace("|", "\\\\|")
        lines.append(f"| {column.name} | {column.dtype} | {column.missing_count} ({column.missing_rate:.1%}) | {column.unique_count} | {detail} |")
    lines.extend(["", "## Data quality warnings", ""])
    lines.extend([f"- {warning}" for warning in report.warnings] if report.warnings else ["- No missingness, duplicate-row, or IQR outlier flags were detected."])
    lines.extend(["", "## Numeric correlations", ""])
    if report.numeric_correlations:
        for column, values in report.numeric_correlations.items():
            pairs = ", ".join(f"{name}: {value:.3f}" if value is not None else f"{name}: N/A" for name, value in values.items())
            lines.append(f"- **{column}:** {pairs}")
    else:
        lines.append("- Fewer than two numeric columns; correlation matrix not generated.")
    lines.extend(["", "> Correlation is descriptive and does not establish causation. IQR flags are prompts for inspection, not automatic deletion rules.", ""])
    return "\n".join(lines)
