"""Validate AI chart proposals against the actual dataset and declared metadata."""
from __future__ import annotations

import pandas as pd

from schemas.chart_plan import ChartPlan
from schemas.eda import EDAReport


def validate_chart_plan(
    plan: ChartPlan,
    frame: pd.DataFrame,
    report: EDAReport | None = None,
) -> None:
    """Raise ValueError for unsupported, redundant-shape or data-incompatible charts."""
    chart_ids: set[str] = set()
    figure_labels: set[str] = set()
    ranks = [spec.rank for spec in plan.charts]
    if len(ranks) != len(set(ranks)):
        raise ValueError("Duplicate chart rank")
    if ranks != list(range(1, len(ranks) + 1)):
        raise ValueError("Chart ranks must be unique, ascending and contiguous from 1")

    profiles = {column.name: column for column in report.dataset.columns} if report else {}

    for spec in plan.charts:
        if spec.chart_id in chart_ids:
            raise ValueError(f"Duplicate chart_id: {spec.chart_id}")
        if spec.figure_label in figure_labels:
            raise ValueError(f"Duplicate figure_label: {spec.figure_label}")
        chart_ids.add(spec.chart_id)
        figure_labels.add(spec.figure_label)

        for name in (spec.x, spec.y):
            if name is not None and name not in frame.columns:
                raise ValueError(f"Unknown column for {spec.chart_id}: {name}")

        if spec.chart_type in ("histogram", "box_plot", "scatter"):
            required_numeric = [spec.x, spec.y] if spec.chart_type == "scatter" else [spec.x]
            for column in required_numeric:
                if not pd.api.types.is_numeric_dtype(frame[column]):
                    raise ValueError(
                        f"Numeric column required for {spec.chart_id}: {column}"
                    )

        if spec.chart_type == "time_series":
            if not pd.api.types.is_numeric_dtype(frame[spec.y]):
                raise ValueError(
                    f"Numeric y column required for {spec.chart_id}: {spec.y}"
                )
            dates = pd.to_datetime(frame[spec.x], errors="coerce")
            values = pd.to_numeric(frame[spec.y], errors="coerce")
            valid_pairs = pd.DataFrame({"date": dates, "value": values}).dropna()
            if len(valid_pairs) < 3:
                raise ValueError(
                    f"Time series needs at least 3 valid date/value pairs: {spec.x}, {spec.y}"
                )

        if spec.chart_type == "scatter":
            if frame[[spec.x, spec.y]].dropna().shape[0] < 2:
                raise ValueError(
                    f"Scatter requires at least two complete observations: {spec.x}, {spec.y}"
                )

        if spec.chart_type == "bar":
            if pd.api.types.is_numeric_dtype(frame[spec.x]):
                raise ValueError(
                    f"Bar chart requires a categorical x column: {spec.x}"
                )
            if frame[spec.x].dropna().empty:
                raise ValueError(f"Category chart needs nonempty observations: {spec.x}")

        if spec.chart_type in ("histogram", "box_plot"):
            values = pd.to_numeric(frame[spec.x], errors="coerce").dropna()
            if values.empty:
                raise ValueError(f"No valid numeric observations for {spec.chart_id}: {spec.x}")

        if report:
            for field_name, column_name, declared_unit in (
                ("x_unit", spec.x, spec.x_unit),
                ("y_unit", spec.y, spec.y_unit),
            ):
                if column_name is None or declared_unit is None:
                    continue
                profile = profiles.get(column_name)
                expected_unit = profile.unit if profile else None
                if not expected_unit or declared_unit != expected_unit:
                    raise ValueError(
                        f"Unsupported {field_name} for {spec.chart_id}: "
                        f"{declared_unit!r}; only explicitly declared unit "
                        f"{expected_unit!r} is allowed for {column_name}."
                    )
