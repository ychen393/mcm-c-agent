"""Execute approved chart types only; persist quantitative plot metadata."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from schemas.chart_plan import ChartPlan, ChartResult
from tools.chart_plan_validator import validate_chart_plan

def execute_chart_plan(plan: ChartPlan, frame: pd.DataFrame, output: Path, sha256: str) -> list[ChartResult]:
    validate_chart_plan(plan, frame)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in plan.charts:
        fig, ax = plt.subplots(figsize=(7, 4))
        metrics = {}
        try:
            if spec.chart_type in ("histogram", "box_plot"):
                s = pd.to_numeric(frame[spec.x], errors="coerce").dropna()
                if spec.chart_type == "histogram":
                    ax.hist(s, bins=min(30, max(5, int(len(s)**0.5))))
                else:
                    ax.boxplot(s)
                n = len(s)
                metrics = {"count": n, "min": float(s.min()), "max": float(s.max()), "median": float(s.median())}
            elif spec.chart_type == "time_series":
                data = pd.DataFrame({"date": pd.to_datetime(frame[spec.x], errors="coerce"),
                    "value": pd.to_numeric(frame[spec.y], errors="coerce")}).dropna().sort_values("date")
                if len(data) < 3:
                    raise ValueError("Time series needs at least 3 valid date/value pairs")
                ax.plot(data["date"], data["value"], linewidth=1.5, label=spec.legend[0] if spec.legend else None)
                fig.autofmt_xdate()
                n = len(data)
                metrics = {"count": n, "first": float(data["value"].iloc[0]), "last": float(data["value"].iloc[-1]),
                    "min": float(data["value"].min()), "max": float(data["value"].max())}
            elif spec.chart_type == "bar":
                counts = frame[spec.x].dropna().astype(str).value_counts().head(15)
                ax.bar(counts.index, counts.values)
                ax.tick_params(axis="x", rotation=30)
                n = int(counts.sum())
                metrics = {"count": n, "categories_shown": len(counts)}
            elif spec.chart_type == "scatter":
                pair = frame[[spec.x, spec.y]].dropna()
                ax.scatter(pair[spec.x], pair[spec.y], s=14)
                n = len(pair)
                metrics = {"count": n}
            else:
                raise ValueError(f"Unsupported chart type: {spec.chart_type}")
            ax.set(title=spec.title,
                xlabel=spec.x_label + (f" ({spec.x_unit})" if spec.x_unit else ""),
                ylabel=spec.y_label + (f" ({spec.y_unit})" if spec.y_unit else ""))
            if spec.legend and spec.chart_type == "time_series": ax.legend()
            fig.tight_layout()
            path = output / f"{spec.chart_id}.png"
            fig.savefig(path, dpi=150)
            results.append(ChartResult(chart_id=spec.chart_id, figure_label=spec.figure_label,
                path=str(path), source_sha256=sha256, spec=spec, plotted_rows=n, metrics=metrics))
        finally:
            plt.close(fig)
    return results
