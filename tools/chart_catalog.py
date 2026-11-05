"""Deterministic fallback chart selection; agent planning comes in Phase B."""
from schemas.chart_plan import ChartPlan, ChartSpec

def fallback_chart_plan(report) -> ChartPlan:
    numeric = [x.name for x in report.dataset.columns if x.numeric_summary is not None]
    dates = [x.name for x in report.dataset.columns if x.datetime_min is not None]
    profiles = {x.name: x for x in report.dataset.columns}
    charts = []
    for i, column in enumerate(numeric[:6], 1):
        profile = profiles[column]
        unit = profile.unit
        unit_suffix = f" ({unit})" if unit else ""
        charts.append(ChartSpec(
            chart_id=f"distribution_{i}", chart_type="histogram", title=f"Distribution of {column}",
            figure_label=f"fig:distribution_{i}", x=column, x_label=f"{column}{unit_suffix}", y_label="Frequency (count)",
            x_unit=unit,
            caption=f"Distribution of observed values for {column}{unit_suffix}; missing values excluded.",
            analytical_question=f"How are values of {column} distributed?",
            rationale=f"Examine the spread and shape of observed values in {column}.",
            caveats=["Distribution alone does not imply causality or time ordering."],
        ))
    count = 0
    for date_col in dates:
        for value_col in numeric:
            if count >= 3: break
            count += 1
            unit = profiles[value_col].unit
            unit_suffix = f" ({unit})" if unit else ""
            period = f" from {profiles[date_col].datetime_min[:10]} to {profiles[date_col].datetime_max[:10]}"
            charts.append(ChartSpec(
                chart_id=f"trend_{count}", chart_type="time_series",
                title=f"{value_col} over {date_col}", figure_label=f"fig:trend_{count}",
                x=date_col, y=value_col, x_label=date_col, y_label=f"{value_col}{unit_suffix}",
                y_unit=unit,
                caption=f"Observed {value_col}{unit_suffix} across {date_col}{period}, ordered chronologically; missing pairs excluded.",
                analytical_question=f"How does {value_col} change over {date_col}?",
                rationale=f"Inspect temporal movement in {value_col} for trends and discontinuities.",
                priority="recommended", rank=len(charts) + 1, relevance_score=0.5,
                analytical_role="trend", caveats=["Descriptive trend; not a prediction."],
            ))
        if count >= 3: break
    return ChartPlan(charts=charts[:12], skipped_reasons=["Semantic selection requires a later Visual EDA Agent."])
