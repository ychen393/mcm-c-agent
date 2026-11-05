"""Validate charts against real data, with strict type/sample-size checks."""
from __future__ import annotations
import pandas as pd
from schemas.chart_plan import ChartPlan

def validate_chart_plan(plan: ChartPlan, frame: pd.DataFrame) -> None:
    ids: set[str] = set()
    labels: set[str] = set()
    ranks: set[int] = set()
    ordered_ranks = [spec.rank for spec in plan.charts]
    if len(ordered_ranks) != len(set(ordered_ranks)):
        raise ValueError("Duplicate chart rank")
    if ordered_ranks != sorted(ordered_ranks):
        raise ValueError("Charts must be ordered by ascending rank")
    for spec in plan.charts:
        if spec.chart_id in ids or spec.figure_label in labels:
            raise ValueError("Duplicate chart_id or figure_label")
        ids.add(spec.chart_id)
        labels.add(spec.figure_label)
        ranks.add(spec.rank)
        for name in [spec.x, spec.y]:
            if name is not None and name not in frame.columns:
                raise ValueError(f"Unknown column: {name}")
        if spec.chart_type in ("histogram", "scatter", "box_plot"):
            cols = [spec.x, spec.y] if spec.chart_type == "scatter" else [spec.x]
            for col in cols:
                if not pd.api.types.is_numeric_dtype(frame[col]):
                    raise ValueError(f"Numeric column required: {col}")
        if spec.chart_type == "time_series":
            if not pd.api.types.is_numeric_dtype(frame[spec.y]):
                raise ValueError(f"Numeric column required: {spec.y}")
            dt = pd.to_datetime(frame[spec.x], errors="coerce")
            if dt.notna().sum() < 3:
                raise ValueError(f"Time series needs >=3 valid dates: {spec.x}")
        if spec.chart_type == "scatter" and frame[[spec.x, spec.y]].dropna().shape[0] < 2:
            raise ValueError("Scatter requires at least two complete observations")
        if spec.chart_type == "bar" and frame[spec.x].dropna().empty:
            raise ValueError("Category chart needs nonempty observations")
        if spec.chart_type in ("histogram", "box_plot") and frame[spec.x].dropna().empty:
            raise ValueError("No valid numeric observations")
