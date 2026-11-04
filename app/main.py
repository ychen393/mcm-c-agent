import streamlit as st

from core.config import get_settings
from core.graph import build_foundation_graph
from core.state import new_research_state
from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report
from tools.eda_artifacts import save_eda_artifacts

settings = get_settings()
st.set_page_config(page_title=settings.app_name, page_icon="🧮", layout="wide")
st.title("MCM C Research Lab")
st.caption("A semi-autonomous research workspace for MCM Problem C")

with st.sidebar:
    st.subheader("Workspace")
    st.info("M1-A · Data-to-EDA")
    st.caption(f"Environment: {settings.app_env}")
    st.caption(f"LLM provider: {settings.llm_provider}")

left, right = st.columns([1.3, 1])
with left:
    st.subheader("Create a research project")
    project_name = st.text_input("Project name", value="MCM C Demo Project")
    problem_text = st.text_area("Problem statement", height=180)
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
    st.metric("Milestone", "M1-A")
    st.metric("Workflow nodes", "2")
    st.metric("Configured provider", settings.llm_provider)
    st.info("EDA calculations run locally with Python. No LLM call is made in this slice.")

st.divider()
st.header("Dataset Explorer")
st.write("Upload one CSV or XLSX dataset to generate a reproducible profile and exploratory analysis.")
project_id = st.text_input("Project ID for saved artifacts", value="mcm-c-demo")
uploaded_file = st.file_uploader("Choose a dataset", type=["csv", "xlsx"], help="Maximum file size: 20 MB.")
if uploaded_file is not None:
    try:
        dataset = load_dataset(uploaded_file.getvalue(), uploaded_file.name)
        st.success(f"Loaded {dataset.file_name}: {len(dataset.frame):,} rows × {len(dataset.frame.columns)} columns")
        st.dataframe(dataset.frame.head(20), use_container_width=True)
        st.caption(f"SHA-256: {dataset.sha256}")
        with st.expander("Dataset context (optional)", expanded=False):
            data_source = st.text_input("Data source", placeholder="e.g., World Bank / Kaggle / official competition dataset", key="eda_data_source")
            frequency_choice = st.selectbox(
                "Data frequency",
                ["Not specified — estimate from dates", "Daily", "Weekly", "Monthly", "Quarterly", "Annual", "Irregular"],
                key="eda_frequency",
            )
            units_text = st.text_area(
                "Column units (one per line: column_name = unit)",
                placeholder="USD (PM) = USD per metric tonne\nDate = YYYY-MM-DD",
                key="eda_column_units",
                height=80,
            )
        if st.button("Run EDA", type="primary"):
            column_units = {}
            invalid_unit_lines = []
            for line in units_text.splitlines():
                if not line.strip():
                    continue
                if "=" not in line:
                    invalid_unit_lines.append(line)
                    continue
                column_name, unit = line.split("=", 1)
                if not column_name.strip() or not unit.strip():
                    invalid_unit_lines.append(line)
                else:
                    column_units[column_name.strip()] = unit.strip()
            unknown_unit_columns = sorted(set(column_units) - set(dataset.frame.columns.astype(str)))
            if invalid_unit_lines:
                st.error("Invalid unit mapping. Use one 'column_name = unit' entry per line.")
            elif unknown_unit_columns:
                st.error(f"Unit mappings reference unknown columns: {', '.join(unknown_unit_columns)}")
            else:
                frequency_value = None if frequency_choice.startswith("Not specified") else frequency_choice
                report = build_eda_report(
                    dataset, project_id, data_source=data_source,
                    temporal_frequency=frequency_value, column_units=column_units,
                )
                artifacts = save_eda_artifacts(dataset, report, settings.output_dir)
                st.session_state["eda_report"] = report.model_dump(mode="json")
                st.session_state["eda_artifacts"] = artifacts
                st.success("EDA completed. Reports and charts have been saved.")
    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Dataset processing failed: {exc}")

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
    context_cols[0].metric("Period start", dataset_meta.get("period_start", "N/A")[:10] if dataset_meta.get("period_start") else "N/A")
    context_cols[1].metric("Period end", dataset_meta.get("period_end", "N/A")[:10] if dataset_meta.get("period_end") else "N/A")
    context_cols[2].metric("Declared frequency", dataset_meta.get("temporal_frequency") or "Not specified")
    inferred_short = (dataset_meta.get("inferred_frequency") or "N/A").split(" (")[0]
    context_cols[3].metric("Estimated frequency", inferred_short)
    st.caption(f"Period: {dataset_meta.get('period_start') or 'N/A'} → {dataset_meta.get('period_end') or 'N/A'}")
    if dataset_meta.get("inferred_frequency"):
        st.caption(f"Frequency estimate: {dataset_meta['inferred_frequency']}")
    if dataset_meta.get("data_source"):
        st.caption(f"Source: {dataset_meta['data_source']}")
    if dataset_meta.get("column_units"):
        st.dataframe(
            [{"Column": name, "Unit": unit} for name, unit in dataset_meta["column_units"].items()],
            hide_index=True, use_container_width=True,
        )
    if artifacts["chart_paths"]:
        st.subheader("EDA Charts & Evidence")
        metric_labels = {
            "count": "Observations", "median": "Median", "min": "Minimum", "max": "Maximum",
            "mean": "Mean", "first": "First value", "last": "Last value",
            "change": "Absolute change", "change_pct": "Change (%)",
        }
        for chart_index, chart_path in enumerate(artifacts["chart_paths"], start=1):
            meta = next((m for m in report_data.get("chart_metadata", []) if m["path"] == chart_path), None)
            if meta:
                spec = meta["spec"]
                st.markdown(f"### Figure {chart_index:02d} · {spec['title']}")
                st.caption(f"LaTeX reference: \\label{{{spec['figure_label']}}}")
                st.image(chart_path, caption=spec["caption"], use_container_width=True)
                st.markdown(f"**Figure ID:** {spec['figure_label']}")
                st.markdown(f"**Analytical question:** {spec['analytical_question']}")
                st.caption(f"Axes: {spec['x_label']} / {spec['y_label']} · Plotted rows: {meta['plotted_rows']}")
                preferred_order = (["count", "median", "min", "max"] if spec["chart_type"] in ("histogram", "box_plot")
                                   else ["count", "first", "last", "change_pct", "min", "max"])
                selected_metrics = [(metric_labels.get(k, k), meta["metrics"][k]) for k in preferred_order
                                    if k in meta["metrics"] and meta["metrics"][k] is not None]
                if selected_metrics:
                    metric_cols = st.columns(min(4, len(selected_metrics)))
                    for metric_index, (label, value) in enumerate(selected_metrics[:4]):
                        display_value = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else str(value)
                        metric_cols[metric_index % len(metric_cols)].metric(label, display_value)
                st.caption(f"Source columns: {', '.join(meta.get('source_columns', [spec['x']]))} · Dataset SHA-256: {meta['source_sha256'][:12]}…")
                with st.expander("Technical metrics (JSON)"):
                    st.json(meta["metrics"])
                st.info("Insight generation is not part of Phase A. Evidence-grounded Observation / Finding / Insight will be added in Phase C.")
            else:
                st.image(chart_path, caption=chart_path.split("/")[-1], use_container_width=True)
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
