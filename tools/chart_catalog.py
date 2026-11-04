"""Deterministic fallback chart selection; agent planning comes in Phase B."""
from schemas.chart_plan import ChartPlan, ChartSpec

def fallback_chart_plan(report) -> ChartPlan:
    numeric = [x.name for x in report.dataset.columns if x.numeric_summary is not None]
    dates = [x.name for x in report.dataset.columns if x.datetime_min is not None]
    charts = []
    for i, column in enumerate(numeric[:6], 1):
        charts.append(ChartSpec(
            chart_id=f"distribution_{i}", chart_type="histogram", title=f"Distribution of {column}",
            figure_label=f"fig:distribution_{i}", x=column, x_label=column, y_label="Frequency (count)",
            caption=f"Distribution of observed values for {column}; missing values excluded.",
            analytical_question=f"How are values of {column} distributed?",
            rationale=f"Examine the spread and shape of observed values in {column}.",
            caveats=["Distribution alone does not imply causality or time ordering."],
        ))
    count = 0
    for date_col in dates:
        for value_col in numeric:
            if count >= 3: break
            count += 1
            charts.append(ChartSpec(
                chart_id=f"trend_{count}", chart_type="time_series",
                title=f"{value_col} over {date_col}", figure_label=f"fig:trend_{count}",
                x=date_col, y=value_col, x_label=date_col, y_label=value_col,
                caption=f"Observed {value_col} across {date_col}, ordered chronologically; missing pairs excluded.",
                analytical_question=f"How does {value_col} change over {date_col}?",
                rationale=f"Inspect temporal movement in {value_col} for trends and discontinuities.",
                caveats=["Descriptive trend; not a prediction."],
            ))
        if count >= 3: break
    return ChartPlan(charts=charts[:12], skipped_reasons=["Semantic selection requires a later Visual EDA Agent."])
