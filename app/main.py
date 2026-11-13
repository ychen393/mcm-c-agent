import json

import streamlit as st

from agents.visual_eda_agent import plan_visual_eda
from app.api_settings import SESSION_REVISION_KEY, build_runtime_settings, render_api_settings
from app.dataset_workspace import (
    approval_identity,
    chart_planning_allowed,
    describe_independent_eda,
    pending_plan_matches,
)
from app.eda_plan_panel import render_problem_aware_eda_panel
from app.foundation_panel import (
    INIT_MESSAGE,
    compute_form_signature,
    mark_project_initialized,
    render_project_phases,
    sync_foundation_state,
)
from app.literature_panel import render_literature_evidence_panel
from app.modeling_panel import render_modeling_experiment_panel
from app.persistence_panel import get_or_create_store, render_persistence_panel
from app.problem_analyst_panel import render_problem_analyst_panel
from app.progress_chrome import derive_progress_chrome
from app.relationship_panel import render_relationship_panel
from app.research_h1_panel import render_research_h1_panel
from app.paper_h3_panel import render_paper_h3_panel
from app.validation_h2_panel import render_validation_h2_panel
from core.config import get_settings
from database.repositories import build_project_store
from schemas.chart_plan import ChartPlan
from schemas.eda import EDAReport
from tools.chart_catalog import fallback_chart_plan
from tools.chart_plan_validator import validate_chart_plan
from tools.data_loader import safe_project_id
from tools.dataset_bundle import (
    ABSOLUTE_MAX_DATASETS,
    DatasetBundle,
    build_bundle_profiles,
    build_dataset_bundle,
)
from tools.eda_artifacts import save_eda_artifacts
from tools.eda_engine import build_eda_report
from tools.eda_persistence import (
    build_compact_eda_report,
    compact_relationship_summary,
    persist_approved_eda_into_state,
)
from tools.intake_errors import classify_upload_errors, format_intake_error_messages
from tools.relationship_profiler import profile_relationships

base_settings = get_settings()
st.set_page_config(page_title=base_settings.app_name, page_icon="🧮", layout="wide")
settings = build_runtime_settings(
    base_settings, st.session_state.get("llm_session_config")
)
page = st.sidebar.radio("Navigation", ["Research Lab", "API Settings"], key="workspace_navigation")
if page == "API Settings":
    render_api_settings(base_settings)
    st.stop()

st.title("MCM C Research Lab")
st.caption("A semi-autonomous research workspace for MCM Problem C")

FREQUENCY_OPTIONS = [
    "Not specified — estimate from dates",
    "Business-day daily",
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Annual",
    "Irregular",
]


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
    config_revision: int,
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
            "config_revision": config_revision,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


_DATASET_CONTEXT_KEYS = ("eda_data_source", "eda_frequency", "eda_column_units")


def _remember_dataset_context() -> None:
    """Copy typed dataset notes out of widget state before a selection change."""
    for key in _DATASET_CONTEXT_KEYS:
        if key in st.session_state:
            st.session_state[f"kept_{key}"] = st.session_state[key]


def _restore_dataset_context() -> None:
    """Put saved notes back when the single-file fields are created again."""
    for key in _DATASET_CONTEXT_KEYS:
        kept = f"kept_{key}"
        if key not in st.session_state and kept in st.session_state:
            st.session_state[key] = st.session_state[kept]


def _clear_saved_report() -> None:
    st.session_state.pop("eda_report", None)
    st.session_state.pop("eda_artifacts", None)
    st.session_state.pop("eda_report_dataset_sha", None)
    st.session_state.pop("eda_report_project_id", None)


def _saved_report_matches_current(file_identity: str | None, project_id: str) -> bool:
    """Show an approved report only for the file and project that produced it."""
    return pending_plan_matches(
        st.session_state.get("eda_report_dataset_sha"),
        file_identity,
    ) and st.session_state.get("eda_report_project_id") == project_id


def _drop_stale_approval(current_identity: str | None) -> None:
    """Drop plan and report state that does not belong to the current dataset.

    ``current_identity`` is the single-file SHA-256, or None when the selection
    is empty, rejected, too large, or more than one file. A project-ID change
    keeps the saved report in session and hides it until that project returns.
    Widget values the user typed (source, units, frequency, problem text) stay.
    """
    plan_identity = st.session_state.get("eda_pending_dataset_sha")
    plan_is_stale = bool(plan_identity) and not pending_plan_matches(
        plan_identity, current_identity
    )
    report_identity = st.session_state.get("eda_report_dataset_sha")
    report_is_stale = bool(report_identity) and not pending_plan_matches(
        report_identity, current_identity
    )
    if plan_is_stale:
        _clear_pending_plan()
        st.info("The uploaded dataset changed. The previous unapproved chart plan was cleared.")
    if report_is_stale:
        _clear_saved_report()
        if not plan_is_stale:
            st.info("The uploaded dataset changed. The previous saved report was cleared.")


def _numeric_stat(column: dict, key: str):
    summary = column["numeric_summary"] or {}
    return summary.get(key)


def _render_independent_profile(view: dict, preview) -> None:
    st.caption(
        f"Analytical scope: independent · not joined · Dataset ID `{view['dataset_id']}`"
    )
    summary = view["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{summary['row_count']:,}")
    c2.metric("Columns", summary["column_count"])
    c3.metric("Numeric columns", summary["numeric_column_count"])
    c4.metric("Columns with missing values", summary["columns_with_missing_values"])
    st.caption(f"SHA-256: {view['sha256']}")
    st.caption(f"File: {view['file_name']} · Display name: {view['display_name']}")
    st.dataframe(preview, use_container_width=True)
    st.subheader("Column profiles")
    st.dataframe(
        [
            {
                "Qualified column": column["qualified_name"],
                "Column": column["name"],
                "Type": column["dtype"],
                "Missing": column["missing_count"],
                "Missing rate": f"{column['missing_rate']:.1%}",
                "Unique": column["unique_count"],
                "Unit": column["unit"] or "Not provided",
                "Mean": _numeric_stat(column, "mean"),
                "Median": _numeric_stat(column, "median"),
                "Min": _numeric_stat(column, "min"),
                "Max": _numeric_stat(column, "max"),
            }
            for column in view["columns"]
        ],
        use_container_width=True,
    )
    if view["warnings"]:
        st.subheader("Data quality warnings")
        for warning in view["warnings"]:
            st.warning(warning)
    context_cols = st.columns(4)
    context_cols[0].metric("Period start", (view["period_start"] or "N/A")[:10])
    context_cols[1].metric("Period end", (view["period_end"] or "N/A")[:10])
    context_cols[2].metric("Declared frequency", view["temporal_frequency"] or "Not specified")
    inferred = (view["inferred_frequency"] or "N/A").split(" (")[0]
    context_cols[3].metric("Estimated frequency", inferred)
    if view["data_source"]:
        st.caption(f"Source: {view['data_source']}")
    correlations = view["correlations_within_dataset"]
    if correlations:
        with st.expander("Correlations within this dataset"):
            st.dataframe(
                [
                    {"Row": row, "Column": column, "Correlation": value}
                    for row, values in correlations.items()
                    for column, value in values.items()
                ],
                use_container_width=True,
            )


def _render_multi_dataset_eda(bundle: DatasetBundle) -> None:
    st.info(
        "Each file is profiled on its own. This step does not join files, "
        "align dates, draw a cross-dataset chart, or call a model."
    )
    for note in bundle.manifest.limitations:
        st.caption(note)
    st.caption(f"Bundle fingerprint: {bundle.fingerprint}")
    st.dataframe(
        [
            {
                "Dataset ID": ref.dataset_id,
                "Display name": ref.display_name,
                "File": ref.file_name,
                "Rows": len(bundle.loaded_dataset(ref.dataset_id).frame),
                "SHA-256": ref.sha256,
                "Qualified columns": ", ".join(ref.qualified_column_names),
            }
            for ref in bundle.datasets
        ],
        use_container_width=True,
    )
    sources: dict[str, str] = {}
    frequencies: dict[str, str | None] = {}
    units: dict[str, dict[str, str]] = {}
    for ref in bundle.datasets:
        with st.expander(f"Dataset context · {ref.display_name}", expanded=False):
            st.caption(f"Dataset ID: {ref.dataset_id}")
            sources[ref.dataset_id] = st.text_input(
                "Data source",
                placeholder="Optional source name or URL",
                key=f"eda_source_{ref.dataset_id}",
            )
            frequency_choice = st.selectbox(
                "Data frequency",
                FREQUENCY_OPTIONS,
                key=f"eda_frequency_{ref.dataset_id}",
            )
            frequencies[ref.dataset_id] = (
                None if frequency_choice.startswith("Not specified") else frequency_choice
            )
            units_text = st.text_area(
                "Column units (one per line: column_name = unit)",
                key=f"eda_units_{ref.dataset_id}",
                height=80,
            )
            try:
                units[ref.dataset_id] = _parse_units(units_text, ref.column_names)
            except ValueError as exc:
                units[ref.dataset_id] = {}
                st.error(str(exc))
    # Stash notes for the post-sync problem-aware plan panel (avoids stale specs).
    st.session_state["eda_bundle_units"] = units
    st.session_state["eda_bundle_frequencies"] = frequencies
    st.session_state["eda_bundle_sources"] = sources
    profiles = build_bundle_profiles(
        bundle,
        column_units_by_dataset=units,
        data_source_by_dataset=sources,
        temporal_frequency_by_dataset=frequencies,
    )
    tabs = st.tabs([f"{ref.display_name} · {ref.dataset_id}" for ref in bundle.datasets])
    for tab, ref in zip(tabs, bundle.datasets, strict=True):
        with tab:
            view = describe_independent_eda(ref, profiles[ref.dataset_id])
            preview = bundle.loaded_dataset(ref.dataset_id).frame.head(20)
            _render_independent_profile(view, preview)
    render_relationship_panel(
        bundle,
        column_units_by_dataset=units,
        temporal_frequency_by_dataset=frequencies,
    )
    if st.button(
        "Record independent EDA summaries into project state",
        key="persist_multi_eda_summaries",
        help=(
            "Stores sanitized per-dataset summaries and relationship metadata. "
            "Does not store rows, bytes, or a merged table."
        ),
    ):
        recorded = st.session_state.get("last_run")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error("Initialize the project before recording EDA into project state.")
        else:
            try:
                rel = profile_relationships(
                    bundle,
                    column_units_by_dataset=units,
                    temporal_frequency_by_dataset=frequencies,
                )
                plan_payload = st.session_state.get("problem_aware_eda_plan")
                confirmation = st.session_state.get("integration_preview_confirmation")
                compact = build_compact_eda_report(
                    project_id=bundle.project_id,
                    bundle_fingerprint=bundle.fingerprint,
                    profiles=list(profiles.values()),
                    plan=plan_payload,
                    relationship_summary=compact_relationship_summary(rel),
                    integration_confirmation=(
                        confirmation if isinstance(confirmation, dict) else None
                    ),
                    mode="independent_multi",
                )
                form_sig = st.session_state.get("foundation_input_signature")
                if not form_sig:
                    st.error("Foundation signature missing; re-initialize the project.")
                else:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_approved_eda_into_state(
                        store,
                        project_id=str(recorded.get("project_id") or bundle.project_id),
                        project_name=str(
                            recorded.get("project_name") or project_name
                        ),
                        state=recorded,
                        input_signature=str(form_sig),
                        compact_eda=compact,
                        note="phase3-independent-multi-eda",
                    )
                    st.session_state["last_run"] = saved
                    st.success(
                        "Independent EDA summaries recorded. "
                        f"lifecycle={saved.get('lifecycle')} · joined=false"
                    )
            except Exception as exc:
                st.error(f"Failed to record EDA state: {type(exc).__name__}: {exc}")


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
            score_col.metric(
                "Relevance",
                f"{chart.relevance_score:.0%}" if plan.strategy == "agent" else "Not scored",
            )
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
    st.subheader("Environment")
    st.caption(f"Environment: {settings.app_env}")
    st.caption(f"LLM provider: {settings.llm_provider}")
    st.caption(f"LLM model: {settings.llm_model}")
    st.caption(f"Problem Analyst LLM: {settings.problem_analyst_use_llm}")
    st.caption(f"Literature live retrieval: {settings.literature_live_retrieval}")
    st.caption(f"Research Strategy LLM: {settings.research_strategy_use_llm}")

st.subheader("Create a research project")
project_name = st.text_input("Project name", value="MCM C Demo Project")
project_id = st.text_input(
    "Project ID for saved artifacts",
    value="mcm-c-demo",
    help="Dataset Explorer and the foundation state both use this project ID.",
)
problem_text = st.text_area(
    "MCM problem statement / research question",
    height=180,
    help=(
        "Problem Analyst turns this into a validated ProblemSpecification. "
        "The Visual EDA Planner also uses it for chart relevance."
    ),
)
st.caption(
    "Initialize records this project and any validated datasets already loaded below. "
    "Problem Analyst can structure the statement without starting joint modeling. "
    "Lab progress (Project → EDA → Literature → H1 → Modeling → H2 → Paper → H3) "
    "updates from the recorded run after initialize."
)
if st.button("Initialize project", type="primary"):
    if len(project_name.strip()) < 3:
        st.error("Project name must contain at least 3 characters.")
    else:
        try:
            safe_project_id(project_id)
        except ValueError as exc:
            st.error(str(exc))
        else:
            mark_project_initialized()
            st.success(INIT_MESSAGE)

st.divider()
st.header("Dataset Explorer")
st.write(
    "Upload 1 to 5 CSV or XLSX files. Each file is profiled on its own with a stable dataset ID. "
    "A single file can still prepare a chart plan. Multiple files are not joined. "
    "Saved artifacts use the project ID from the form above."
)
uploaded_files = st.file_uploader(
    "Choose 1 to 5 datasets",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
    help="CSV or XLSX. Up to 5 files, 20 MB each, 50 MB combined. Files are not joined.",
    key="dataset_uploader",
)
uploaded_files = list(uploaded_files or [])
upload_payloads = [(uploaded.name, uploaded.getvalue()) for uploaded in uploaded_files]
accepted_identity: str | None = None
bundle: DatasetBundle | None = None
bundle_rejected = False
_remember_dataset_context()

if len(uploaded_files) > ABSOLUTE_MAX_DATASETS:
    bundle_rejected = True
    st.error(
        f"Dataset bundle accepts at most {ABSOLUTE_MAX_DATASETS} files; "
        f"received {len(uploaded_files)}."
    )
    for message in format_intake_error_messages(
        classify_upload_errors(upload_payloads)
    ):
        st.error(message)
    _drop_stale_approval(None)
elif not uploaded_files:
    _drop_stale_approval(None)
else:
    try:
        bundle = build_dataset_bundle(upload_payloads, project_id=project_id)
    except ValueError as exc:
        bundle_rejected = True
        st.error(str(exc))
        for message in format_intake_error_messages(
            classify_upload_errors(upload_payloads)
        ):
            if message != str(exc):
                st.error(message)
        _drop_stale_approval(None)
    except Exception as exc:
        bundle_rejected = True
        st.error(f"Dataset processing failed: {type(exc).__name__}: {exc}")
        for message in format_intake_error_messages(
            classify_upload_errors(upload_payloads)
        ):
            st.error(message)
        _drop_stale_approval(None)
    else:
        dataset_count = len(bundle.datasets)
        single_sha = bundle.datasets[0].sha256 if dataset_count == 1 else None
        accepted_identity = approval_identity(dataset_count, single_sha)
        _drop_stale_approval(accepted_identity)
        if chart_planning_allowed(dataset_count):
            dataset_ref = bundle.datasets[0]
            dataset = bundle.loaded_dataset(dataset_ref.dataset_id)
            st.success(
                f"Loaded {dataset.file_name}: {len(dataset.frame):,} rows × "
                f"{len(dataset.frame.columns)} columns"
            )
            st.dataframe(dataset.frame.head(20), use_container_width=True)
            st.caption(f"Dataset ID: {dataset_ref.dataset_id}")
            st.caption(f"SHA-256: {dataset.sha256}")
            st.caption(
                "Qualified columns: "
                + ", ".join(dataset_ref.qualified_column_names)
            )

            with st.expander("Dataset context (optional)", expanded=False):
                _restore_dataset_context()
                data_source = st.text_input(
                    "Data source",
                    placeholder="e.g., LBMA Gold Price PM / official source URL",
                    key="eda_data_source",
                )
                frequency_choice = st.selectbox(
                    "Data frequency",
                    FREQUENCY_OPTIONS,
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
                help=(
                    "When enabled, the problem statement and compact dataset profile "
                    "are sent to the configured LLM provider."
                ),
            )
            if use_ai_planner:
                st.warning(
                    "External model processing is enabled. The planner sends the problem statement "
                    "and compact column/statistical profile, not the full raw CSV/XLSX rows."
                )
            else:
                st.caption(
                    "AI planning is off. A deterministic generic chart plan "
                    "will be prepared locally."
                )

            if st.button("Generate chart plan", type="primary", key="generate_chart_plan"):
                _clear_pending_plan()
                _clear_saved_report()
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
                                    "AI planner was not enabled; "
                            "generated generic deterministic EDA."
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
                        st.session_state.get(SESSION_REVISION_KEY, 0),
                    )
                    st.success("Chart plan generated. Review it below before approving execution.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Chart planning failed: {type(exc).__name__}: {exc}")

            if "eda_pending_plan" in st.session_state and pending_plan_matches(
                st.session_state.get("eda_pending_dataset_sha"),
                dataset.sha256,
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
                        st.session_state.get(SESSION_REVISION_KEY, 0),
                    )
                    stored_problem = st.session_state.get("eda_pending_problem_statement")
                    stored_signature = st.session_state.get("eda_pending_context_signature")
                    context_changed = (
                        problem_text != stored_problem
                        or current_signature != stored_signature
                    )
                except ValueError as exc:
                    context_changed = True
                    st.warning(str(exc))
                _render_chart_plan(pending_plan)

                if context_changed:
                    st.warning(
                        "The problem statement or dataset metadata changed after "
                        "this plan was created. Generate a new plan before approving it."
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
                        st.session_state["eda_report_project_id"] = pending_report.project_id
                        recorded = st.session_state.get("last_run")
                        form_sig = st.session_state.get("foundation_input_signature")
                        if (
                            isinstance(recorded, dict)
                            and recorded.get("run_id")
                            and form_sig
                        ):
                            profiles = build_bundle_profiles(bundle)
                            plan_payload = st.session_state.get("problem_aware_eda_plan")
                            compact = build_compact_eda_report(
                                project_id=pending_report.project_id,
                                bundle_fingerprint=bundle.fingerprint,
                                profiles=list(profiles.values()),
                                plan=plan_payload,
                                mode="single_file_charts",
                            )
                            # Strip forbidden dense fields from session full report before store.
                            store = get_or_create_store(lambda: build_project_store(settings))
                            saved = persist_approved_eda_into_state(
                                store,
                                project_id=str(
                                    recorded.get("project_id") or pending_report.project_id
                                ),
                                project_name=str(
                                    recorded.get("project_name") or project_name
                                ),
                                state=recorded,
                                input_signature=str(form_sig),
                                compact_eda=compact,
                                artifacts=artifacts,
                                dataset_sha256=dataset.sha256,
                                note="phase3-approved-single-eda",
                            )
                            st.session_state["last_run"] = saved
                        _clear_pending_plan()
                        st.success(
                            "Approved chart plan executed. Reports and charts have been saved."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Chart execution failed: {type(exc).__name__}: {exc}")
        else:
            _render_multi_dataset_eda(bundle)

report_matches_selection = _saved_report_matches_current(accepted_identity, project_id)
saved_project_id = st.session_state.get("eda_report_project_id")
file_still_loaded = pending_plan_matches(
    st.session_state.get("eda_report_dataset_sha"),
    accepted_identity,
)
if (
    "eda_report" in st.session_state
    and file_still_loaded
    and saved_project_id
    and saved_project_id != project_id
):
    st.info(
        f"This saved report was approved for project {saved_project_id}. "
        "It is not shown as output for the current project ID."
    )
if "eda_report" in st.session_state and report_matches_selection:
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

project_store = get_or_create_store(lambda: build_project_store(settings))
llm_revision = int(st.session_state.get(SESSION_REVISION_KEY, 0))
inputs_current = sync_foundation_state(
    project_id=project_id,
    project_name=project_name,
    problem_text=problem_text,
    upload_payloads=upload_payloads,
    bundle=bundle,
    bundle_rejected=bundle_rejected,
    llm_provider=settings.llm_provider,
    llm_model=settings.llm_model,
    llm_config_revision=llm_revision,
    store=project_store,
)
recorded_state = (
    st.session_state.get("last_run") if st.session_state.get("foundation_initialized") else None
)
form_signature = None
computed = compute_form_signature(
    project_id=project_id,
    project_name=project_name,
    problem_text=problem_text,
    upload_payloads=upload_payloads,
    bundle=bundle,
    bundle_rejected=bundle_rejected,
    llm_provider=settings.llm_provider,
    llm_model=settings.llm_model,
    llm_config_revision=llm_revision,
)
if computed is not None:
    form_signature = computed[0]

progress = derive_progress_chrome(
    recorded_state if isinstance(recorded_state, dict) else None
)
with st.sidebar:
    st.subheader("Workspace")
    st.info(progress.sidebar_badge)
    st.caption(progress.stepper_line)

st.subheader("System status")
status_cols = st.columns(3)
status_cols[0].metric("Current stage", progress.milestone_metric)
status_cols[1].metric("Lab progress", progress.progress_metric)
status_cols[2].metric("Configured provider", settings.llm_provider)
st.caption(progress.caption)
st.caption(progress.stepper_line)
st.info(
    "Independent profiles and relationship previews never auto-merge. "
    "Chart execution still requires explicit approval."
)

render_project_phases(recorded_state, inputs_current=inputs_current)
spec_for_eda = render_problem_analyst_panel(
    problem_text,
    settings=settings,
    recorded_state=recorded_state if isinstance(recorded_state, dict) else None,
)
# Problem-aware plan runs after foundation sync + analyst so cleared specs cannot linger.
if bundle is not None and not bundle_rejected:
    render_problem_aware_eda_panel(
        bundle,
        problem_specification=spec_for_eda,
        column_units_by_dataset=st.session_state.get("eda_bundle_units"),
        temporal_frequency_by_dataset=st.session_state.get("eda_bundle_frequencies"),
    )
eda_plan_for_lit = st.session_state.get("problem_aware_eda_plan")
eda_report_for_lit = None
if isinstance(recorded_state, dict):
    maybe_eda = recorded_state.get("eda_report")
    if isinstance(maybe_eda, dict):
        eda_report_for_lit = maybe_eda
render_literature_evidence_panel(
    settings=settings,
    problem_specification=spec_for_eda if isinstance(spec_for_eda, dict) else None,
    eda_plan=eda_plan_for_lit if isinstance(eda_plan_for_lit, dict) else None,
    eda_report=eda_report_for_lit,
    recorded_state=recorded_state if isinstance(recorded_state, dict) else None,
    project_id=project_id,
    project_name=project_name,
    input_signature=form_signature,
)
evidence_for_h1 = None
if isinstance(recorded_state, dict):
    maybe_ev = recorded_state.get("evidence_report")
    if isinstance(maybe_ev, dict) and maybe_ev:
        evidence_for_h1 = maybe_ev
if evidence_for_h1 is None:
    cached_ev = st.session_state.get("literature_evidence_report")
    if isinstance(cached_ev, dict) and cached_ev:
        evidence_for_h1 = cached_ev
render_research_h1_panel(
    settings=settings,
    problem_specification=spec_for_eda if isinstance(spec_for_eda, dict) else None,
    eda_plan=eda_plan_for_lit if isinstance(eda_plan_for_lit, dict) else None,
    eda_report=eda_report_for_lit,
    evidence_report=evidence_for_h1,
    recorded_state=recorded_state if isinstance(recorded_state, dict) else None,
    project_id=project_id,
    project_name=project_name,
    input_signature=form_signature,
)
render_modeling_experiment_panel(
    settings=settings,
    problem_specification=spec_for_eda if isinstance(spec_for_eda, dict) else None,
    recorded_state=recorded_state if isinstance(recorded_state, dict) else None,
    project_id=project_id,
    project_name=project_name,
    input_signature=form_signature,
)
render_validation_h2_panel(
    settings=settings,
    problem_specification=spec_for_eda if isinstance(spec_for_eda, dict) else None,
    recorded_state=recorded_state if isinstance(recorded_state, dict) else None,
    project_id=project_id,
    project_name=project_name,
    input_signature=form_signature,
)
render_paper_h3_panel(
    settings=settings,
    problem_specification=spec_for_eda if isinstance(spec_for_eda, dict) else None,
    recorded_state=recorded_state if isinstance(recorded_state, dict) else None,
    project_id=project_id,
    project_name=project_name,
    input_signature=form_signature,
)
render_persistence_panel(
    project_store,
    project_id=project_id,
    project_name=project_name,
    recorded_state=recorded_state,
    input_signature=form_signature,
)

if recorded_state is not None:
    st.subheader("Latest foundation state")
    st.caption(
        "Recorded when you initialize the project, change inputs, or persist approved EDA. "
        f"run_id={recorded_state.get('run_id')} · lifecycle={recorded_state.get('lifecycle')}"
    )
    with st.expander("Developer / foundation state (JSON)", expanded=False):
        st.caption(
            "uploaded_files holds dataset provenance only (IDs, names, SHA-256, counts, warnings). "
            "Compact eda_report summaries omit raw rows and forbidden dense fields. "
            "File bytes are not stored here, and no trading strategy is modeled."
        )
        st.json(recorded_state)
