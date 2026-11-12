"""Streamlit panel: problem-aware multi-dataset EDA plan (Phase 3)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from schemas.eda_plan import ProblemAwareEDAPlan
from schemas.problem_specification import ProblemSpecification
from tools.dataset_bundle import DatasetBundle
from tools.problem_aware_eda import build_problem_aware_eda_plan
from tools.relationship_profiler import profile_relationships


def render_problem_aware_eda_panel(
    bundle: DatasetBundle,
    *,
    problem_specification: dict[str, Any] | ProblemSpecification | None,
    column_units_by_dataset: dict[str, dict[str, str]] | None = None,
    temporal_frequency_by_dataset: dict[str, str | None] | None = None,
) -> ProblemAwareEDAPlan:
    """Render deterministic EDA guidance tied to ProblemSpecification when present."""
    st.subheader("Problem-aware EDA plan")
    st.caption(
        "Uses ProblemSpecification constraints when available. "
        "Profiles stay independent; joins are suggestions only — never invented or auto-merged."
    )

    relationship_report = None
    if len(bundle.datasets) >= 2:
        relationship_report = profile_relationships(
            bundle,
            column_units_by_dataset=column_units_by_dataset,
            temporal_frequency_by_dataset=temporal_frequency_by_dataset,
        )

    plan = build_problem_aware_eda_plan(
        bundle=bundle,
        problem_specification=problem_specification,
        relationship_report=relationship_report,
    )

    if not plan.has_problem_specification:
        st.info(
            "No ProblemSpecification yet. Run Problem Analyst to condition EDA on "
            "official constraints (e.g. 2022 C past-data-only and supplied CSVs)."
        )
    else:
        st.success(
            f"Plan conditioned on problem_id={plan.problem_id} · "
            f"{plan.title or 'untitled'}"
        )

    if plan.constraint_reminders:
        st.markdown("**Constraint reminders**")
        for item in plan.constraint_reminders:
            st.markdown(
                f"- `{item.constraint_id}` ({item.constraint_kind}): "
                f"{item.eda_implication}"
            )

    if plan.dataset_matches:
        st.markdown("**Dataset ↔ problem file matching**")
        st.dataframe(
            [
                {
                    "Status": match.status,
                    "Upload": match.upload_file_name or "—",
                    "Expected": match.expected_file_name or "—",
                    "Dataset ID": match.dataset_id or "—",
                    "Notes": match.notes,
                }
                for match in plan.dataset_matches
            ],
            use_container_width=True,
            hide_index=True,
        )

    if plan.focus_by_dataset:
        st.markdown("**Independent focus (per dataset)**")
        for focus in plan.focus_by_dataset:
            with st.expander(f"{focus.display_name} · {focus.dataset_id}", expanded=False):
                st.caption("Qualified columns: " + ", ".join(focus.qualified_columns))
                for note in focus.focus_notes:
                    st.write(f"- {note}")

    if plan.suggested_relationships:
        st.markdown("**Cross-dataset relationship suggestions**")
        for item in plan.suggested_relationships:
            label = (
                f"{item.left_display_name} ↔ {item.right_display_name}: "
                f"**{item.stance}**"
            )
            if item.stance == "cannot_join":
                st.error(label)
            elif item.stance == "suggest_preview":
                st.warning(label + " — preview only after you confirm keys.")
            else:
                st.info(label)
            st.caption(item.evidence_summary)
            for caveat in item.caveats:
                st.caption(f"Caveat: {caveat}")

    st.markdown("**Must not**")
    for rule in plan.must_not:
        st.write(f"- {rule}")

    with st.expander("Full problem-aware EDA plan (JSON)", expanded=False):
        st.json(plan.model_dump(mode="json"))

    st.session_state["problem_aware_eda_plan"] = plan.model_dump(mode="json")
    return plan
