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
        if st.button("Run EDA", type="primary"):
            report = build_eda_report(dataset, project_id)
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
            }
            for item in report_data["dataset"]["columns"]
        ],
        use_container_width=True,
    )
    if report_data["warnings"]:
        st.subheader("Data Quality Warnings")
        for warning in report_data["warnings"]:
            st.warning(warning)
    if artifacts["chart_paths"]:
        st.subheader("Numeric Distributions")
        for chart_path in artifacts["chart_paths"]:
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
