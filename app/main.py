import json
import streamlit as st

from core.config import get_settings
from core.graph import build_foundation_graph
from core.state import new_research_state
from schemas.chart_plan import ChartPlan
from schemas.eda import EDAReport
from tools.chart_catalog import fallback_chart_plan
from tools.chart_plan_validator import validate_chart_plan
from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report
from tools.eda_artifacts import save_eda_artifacts
from agents.visual_eda_agent import plan_visual_eda

settings = get_settings()
st.set_page_config(page_title=settings.app_name, page_icon="🧮", layout="wide")
st.title("MCM C Research Lab")
st.caption("A semi-autonomous research workspace for MCM Problem C")

PENDING_KEYS = (
    "eda_pending_plan",
    "eda_pending_report",
    "eda_pending_dataset_sha",
    "eda_pending_problem_statement",
    "eda_pending_context_signature",
)


def _clear_pending_plan() -> None:
    for key in PENDING_KEYS:
        st.session_state.pop(key, None)


def _parse_units(units_text: str, columns: list[str]) -> dict[str, str]:
    column_units: dict[str, str] = {}
    invalid_lines = []
    for line in units_text.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            invalid_lines.append(line)
            continue
        column_name, unit = line.split("=", 1)
        if not column_name.strip() or not unit.strip():
            invalid_lines.append(line)
        else:
            column_units[column_name.strip()] = unit.strip()
    if invalid_lines:
        raise ValueError("Invalid unit mapping. Use one 'column_name = unit' entry per line.")
    unknown = sorted(set(column_units) - set(columns))
    if unknown:
        raise ValueError(f"Unit mappings reference unknown columns: {', '.join(unknown)}")
    return column_units


def _context_signature(
    project_id: str,
    data_source: str,
    frequency: str | None,
    units: dict[str, str],
    use_ai: bool,
    provider: str,
    model: str,
) -> str:
    return json.dumps(
        {
            "project_id": project_id,
            "data_source": data_source.strip(),
            "frequency": frequency,
            "units": units,
            "use_ai": use_ai,
            "provider": provider,
            "model": model,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _render_chart_plan(plan: ChartPlan) -> None:
    st.subheader("Proposed chart plan")
    if plan.strategy == "agent":
        st.success(
            f"AI plan · {plan.planner_provider} / {plan.planner_model} · "
            f"Prompt {plan.planner_prompt_version}"
        )
    else:
        st.info("Deterministic generic EDA plan — this is not problem-aware chart selection.")
        if plan.fallback_reason:
            st.caption(f"Fallback reason: {plan.fallback_reason}")

    if plan.planning_summary:
        st.write(plan.planning_summary)
    if plan.problem_alignment:
        st.caption(f"Problem alignment: {plan.problem_alignment}")

    if not plan.charts:
        st.warning("The planner proposed no charts. Review the omission reasons below.")
    for chart in plan.charts:
        with st.container(border=True):
            rank_col, score_col, type_col = st.columns([0.7, 0.9, 1.2])
            rank_col.metric("Rank", chart.rank)
            score_col.metric("Relevance", f"{chart.relevance_score:.0%}")
            type_col.metric("Chart type", chart.chart_type.replace("_", " ").title())
            st.markdown(f"**{chart.title}** · \\label{{{chart.figure_label}}}")
            st.caption(
                f"Source columns: {chart.x}"
                + (f", {chart.y}" if chart.y else "")
                + f" · Role: {chart.analytical_role} · Priority: {chart.priority}"
            )
            st.write(f"**Analytical question:** {chart.analytical_question}")
            st.write(f"**Why this chart:** {chart.rationale}")
            st.caption(f"Axes: {chart.x_label} / {chart.y_label}")
            if chart.caveats:
                st.caption("Caveats: " + " · ".join(chart.caveats))

    if plan.skipped_reasons:
        with st.expander("Chart ideas not selected and why"):
            for reason in plan.skipped_reasons:
                st.write(f"- {reason}")


with st.sidebar:
    st.subheader("Workspace")
    st.info("M1-B · Visual EDA Agent")
    st.caption(f"Environment: {settings.app_env}")
    st.caption(f"LLM provider: {settings.llm_provider}")

left, right = st.columns([1.3, 1])
with left:
    st.subheader("Create a research project")
    project_name = st.text_input("Project name", value="MCM C Demo Project")
    problem_text = st.text_area(
        "MCM problem statement / research question",
        height=180,
        help="The Visual EDA Planner uses this context to select charts relevant to the research task.",
    )
    if st.button("Initialize project", type="primary"):
        if len(project_name.strip()) < 3:
            st.error("Project name must contain at least 3 characters.")
        else:
            state = new_research_state("demo-project", project_name.strip())
            state["problem_text"] = problem_text
            st.session_state["last_run"] = build_foundation_graph().invoke(state)
            st.success("Foundation workflow completed.")

with right:
    st.subheader("System status")
    st.metric("Milestone", "M1-B")
    st.metric("Workflow nodes", "2")
    st.metric("Configured provider", settings.llm_provider)
    st.info(
        "The planner proposes charts; Python validates and renders them only after your approval."
    )

st.divider()
st.header("Dataset Explorer")
st.write("Upload one CSV or XLSX dataset to profile it and prepare a problem-aware chart plan.")
project_id = st.text_input("Project ID for saved artifacts", value="mcm-c-demo")
uploaded_file = st.file_uploader(
    "Choose a dataset",
    type=["csv", "xlsx"],
    help="Maximum file size: 20 MB.",
)

if uploaded_file is not None:
    try:
        dataset = load_dataset(uploaded_file.getvalue(), uploaded_file.name)
        st.success(
            f"Loaded {dataset.file_name}: {len(dataset.frame):,} rows × "
            f"{len(dataset.frame.columns)} columns"
        )
        st.dataframe(dataset.frame.head(20), use_container_width=True)
        st.caption(f"SHA-256: {dataset.sha256}")

        if (
            st.session_state.get("eda_pending_dataset_sha")
            and st.session_state["eda_pending_dataset_sha"] != dataset.sha256
        ):
            _clear_pending_plan()
            st.info("The uploaded dataset changed. The previous unapproved chart plan was cleared.")

        if (
            st.session_state.get("eda_report_dataset_sha")
            and st.session_state["eda_report_dataset_sha"] != dataset.sha256
        ):
            st.session_state.pop("eda_report", None)
            st.session_state.pop("eda_artifacts", None)
            st.session_state.pop("eda_report_dataset_sha", None)

        with st.expander("Dataset context (optional)", expanded=False):
            data_source = st.text_input(
                "Data source",
                placeholder="e.g., LBMA Gold Price PM / official source URL",
                key="eda_data_source",
            )
            frequency_choice = st.selectbox(
                "Data frequency",
                [
                    "Not specified — estimate from dates",
                    "Business-day daily",
                    "Daily",
                    "Weekly",
                    "Monthly",
                    "Quarterly",
                    "Annual",
                    "Irregular",
                ],
                key="eda_frequency",
            )
            units_text = st.text_area(
                "Column units (one per line: column_name = unit)",
                placeholder="price = USD per troy ounce",
                key="eda_column_units",
                height=80,
            )

        use_ai_planner = st.checkbox(
            "Use AI Visual EDA Planner",
            value=False,
            help="When enabled, the problem statement and compact dataset profile are sent to the configured LLM provider.",
        )
        if use_ai_planner:
            st.warning(
                "External model processing is enabled. The planner sends the problem statement "
                "and compact column/statistical profile, not the full raw CSV/XLSX rows."
            )
        else:
            st.caption(
                "AI planning is off. A deterministic generic chart plan will be prepared locally."
            )

        if st.button("Generate chart plan", type="primary", key="generate_chart_plan"):
            try:
                column_units = _parse_units(
                    units_text,
                    dataset.frame.columns.astype(str).tolist(),
                )
                frequency_value = (
                    None if frequency_choice.startswith("Not specified") else frequency_choice
                )
                report = build_eda_report(
                    dataset,
                    project_id,
                    data_source=data_source,
                    temporal_frequency=frequency_value,
                    column_units=column_units,
                )
                if use_ai_planner:
                    plan = plan_visual_eda(
                        problem_text,
                        report,
                        dataset.frame,
                        settings=settings,
                    )
                else:
                    plan = fallback_chart_plan(report).model_copy(
                        update={
                            "fallback_reason": (
                                "AI planner was not enabled; generated generic deterministic EDA."
                            )
                        }
                    )
                validate_chart_plan(plan, dataset.frame, report)
                st.session_state["eda_pending_plan"] = plan.model_dump(mode="json")
                st.session_state["eda_pending_report"] = report.model_dump(mode="json")
                st.session_state["eda_pending_dataset_sha"] = dataset.sha256
                st.session_state["eda_pending_problem_statement"] = problem_text
                st.session_state["eda_pending_context_signature"] = _context_signature(
                    project_id,
                    data_source,
                    frequency_value,
                    column_units,
                    use_ai_planner,
                    settings.llm_provider,
                    settings.llm_model,
                )
                st.success("Chart plan generated. Review it below before approving execution.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Chart planning failed: {type(exc).__name__}: {exc}")

        if (
            "eda_pending_plan" in st.session_state
            and st.session_state.get("eda_pending_dataset_sha") == dataset.sha256
        ):
            pending_plan = ChartPlan.model_validate(st.session_state["eda_pending_plan"])
            pending_report = EDAReport.model_validate(st.session_state["eda_pending_report"])
            current_frequency = (
                None if frequency_choice.startswith("Not specified") else frequency_choice
            )
            try:
                current_units = _parse_units(
                    units_text,
                    dataset.frame.columns.astype(str).tolist(),
                )
                current_signature = _context_signature(
                    project_id,
                    data_source,
                    current_frequency,
                    current_units,
                    use_ai_planner,
                    settings.llm_provider,
                    settings.llm_model,
                )
                context_changed = (
                    problem_text != st.session_state.get("eda_pending_problem_statement")
                    or current_signature != st.session_state.get("eda_pending_context_signature")
                )
            except ValueError as exc:
                context_changed = True
                st.warning(str(exc))
            _render_chart_plan(pending_plan)

            if context_changed:
                st.warning(
                    "The problem statement or dataset metadata changed after this plan was created. "
                    "Generate a new plan before approving it."
                )

            approve_col, discard_col = st.columns(2)
            with approve_col:
                approve_clicked = st.button(
                    "Approve plan & generate charts",
                    type="primary",
                    disabled=context_changed,
                    key="approve_chart_plan",
                )
            with discard_col:
                discard_clicked = st.button("Discard plan", key="discard_chart_plan")

            if discard_clicked:
                _clear_pending_plan()
                st.rerun()

            if approve_clicked:
                try:
                    artifacts = save_eda_artifacts(
                        dataset,
                        pending_report,
                        settings.output_dir,
                        chart_plan=pending_plan,
                        human_approved=True,
                    )
                    st.session_state["eda_report"] = pending_report.model_dump(mode="json")
                    st.session_state["eda_artifacts"] = artifacts
                    st.session_state["eda_report_dataset_sha"] = dataset.sha256
                    _clear_pending_plan()
                    st.success("Approved chart plan executed. Reports and charts have been saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Chart execution failed: {type(exc).__name__}: {exc}")

    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Dataset processing failed: {type(exc).__name__}: {exc}")

if "eda_report" in st.session_state:
    report_data = st.session_state["eda_report"]
    artifacts = st.session_state["eda_artifacts"]
    st.subheader("EDA Summary")
    summary = report_data["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{summary['row_count']:,}")
    c2.metric("Columns", summary["column_count"])
    c3.metric("Numeric columns", summary["numeric_column_count"])
    c4.metric("Columns with missing values", summary["columns_with_missing_values"])

    approval = summary.get("chart_plan_approval")
    if approval:
        st.caption(
            f"Chart-plan approval: {approval['status']} · "
            f"{approval['approved_at_utc']}"
        )
    st.subheader("Column Profiles")
    st.dataframe(
        [
            {
                "Column": item["name"],
                "Type": item["dtype"],
                "Missing": item["missing_count"],
                "Missing rate": f"{item['missing_rate']:.1%}",
                "Unique": item["unique_count"],
                "IQR outliers": item["outlier_count_iqr"],
                "Unit": item.get("unit") or "Not provided",
            }
            for item in report_data["dataset"]["columns"]
        ],
        use_container_width=True,
    )
    if report_data["warnings"]:
        st.subheader("Data Quality Warnings")
        for warning in report_data["warnings"]:
            st.warning(warning)

    dataset_meta = report_data["dataset"]
    st.subheader("Dataset Context")
    context_cols = st.columns(4)
    context_cols[0].metric(
        "Period start",
        dataset_meta.get("period_start", "N/A")[:10]
        if dataset_meta.get("period_start")
        else "N/A",
    )
    context_cols[1].metric(
        "Period end",
        dataset_meta.get("period_end", "N/A")[:10]
        if dataset_meta.get("period_end")
        else "N/A",
    )
    context_cols[2].metric(
        "Declared frequency",
        dataset_meta.get("temporal_frequency") or "Not specified",
    )
    inferred_short = (dataset_meta.get("inferred_frequency") or "N/A").split(" (")[0]
    context_cols[3].metric("Estimated frequency", inferred_short)
    st.caption(
        f"Period: {dataset_meta.get('period_start') or 'N/A'} → "
        f"{dataset_meta.get('period_end') or 'N/A'}"
    )
    if dataset_meta.get("inferred_frequency"):
        st.caption(f"Frequency estimate: {dataset_meta['inferred_frequency']}")
    if dataset_meta.get("data_source"):
        st.caption(f"Source: {dataset_meta['data_source']}")
    if dataset_meta.get("column_units"):
        st.dataframe(
            [
                {"Column": name, "Unit": unit}
                for name, unit in dataset_meta["column_units"].items()
            ],
            hide_index=True,
            use_container_width=True,
        )

    if artifacts["chart_paths"]:
        st.subheader("EDA Charts & Evidence")
        metric_labels = {
            "count": "Observations",
            "median": "Median",
            "min": "Minimum",
            "max": "Maximum",
            "mean": "Mean",
            "first": "First value",
            "last": "Last value",
            "change": "Absolute change",
            "change_pct": "First-to-last change (%)",
        }
        for chart_index, chart_path in enumerate(artifacts["chart_paths"], start=1):
            meta = next(
                (m for m in report_data.get("chart_metadata", []) if m["path"] == chart_path),
                None,
            )
            if meta:
                spec = meta["spec"]
                st.markdown(f"### Figure {chart_index:02d} · {spec['title']}")
                st.caption(f"LaTeX reference: \\label{{{spec['figure_label']}}}")
                st.image(chart_path, caption=spec["caption"], use_container_width=True)
                st.markdown(f"**Analytical question:** {spec['analytical_question']}")
                st.caption(
                    f"Axes: {spec['x_label']} / {spec['y_label']} · "
                    f"Plotted rows: {meta['plotted_rows']}"
                )
                preferred_order = (
                    ["count", "median", "min", "max"]
                    if spec["chart_type"] in ("histogram", "box_plot")
                    else ["count", "first", "last", "change_pct", "min", "max"]
                )
                selected_metrics = [
                    (metric_labels.get(key, key), meta["metrics"][key])
                    for key in preferred_order
                    if key in meta["metrics"] and meta["metrics"][key] is not None
                ]
                if selected_metrics:
                    metric_cols = st.columns(min(4, len(selected_metrics)))
                    for metric_index, (label, value) in enumerate(selected_metrics[:4]):
                        display_value = (
                            f"{value:,.2f}"
                            if isinstance(value, float)
                            else f"{value:,}"
                            if isinstance(value, int)
                            else str(value)
                        )
                        metric_cols[metric_index % len(metric_cols)].metric(label, display_value)
                st.caption(
                    f"Source columns: {', '.join(meta.get('source_columns', [spec['x']]))} · "
                    f"Dataset SHA-256: {meta['source_sha256'][:12]}…"
                )
                with st.expander("Technical metrics (JSON)"):
                    st.json(meta["metrics"])
            else:
                st.image(chart_path, caption=chart_path.split("/")[-1], use_container_width=True)
    else:
        st.info("No charts were generated for the approved plan.")

    with open(artifacts["report_markdown_path"], "rb") as report_file:
        st.download_button(
            "Download EDA Markdown Report",
            data=report_file,
            file_name="eda_report.md",
            mime="text/markdown",
        )
    with open(artifacts["report_json_path"], "rb") as report_file:
        st.download_button(
            "Download EDA JSON",
            data=report_file,
            file_name="eda_report.json",
            mime="application/json",
        )
    st.caption(f"Artifacts saved under: {settings.output_dir / project_id / 'eda'}")

if "last_run" in st.session_state:
    st.subheader("Latest foundation workflow state")
    st.json(st.session_state["last_run"])
