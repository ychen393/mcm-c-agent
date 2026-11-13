"""Show and refresh the foundation state from the current project form.

The state is written when the user initializes the project, and again when
that user changes the project, the problem text, the file selection, or the
API settings revision. It is not written on unrelated clicks such as a join
preview. API keys are never copied into the state.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.i18n import t
from core.foundation import (
    NOT_IMPLEMENTED,
    build_initialized_state,
    foundation_input_signature,
    selection_token,
)
from core.graph import build_foundation_graph
from core.project_store import ProjectStore
from tools.data_loader import safe_project_id
from tools.dataset_bundle import DatasetBundle

# English identity strings kept for AppTest assertions; display uses t().
INIT_MESSAGE = "Project initialized — analysis not started."
UPDATE_MESSAGE = "Project inputs updated — analysis not started. Previous approvals are stale."

INITIALIZED_KEY = "foundation_initialized"
SIGNATURE_KEY = "foundation_input_signature"
SKIP_NOTICE_KEY = "foundation_skip_update_notice"

_PHASE_ROWS = (
    ("project_initialized", "foundation.phase.project_initialized"),
    ("datasets_loaded", "foundation.phase.datasets_loaded"),
    ("independent_eda", "foundation.phase.independent_eda"),
    ("relationship_preview", "foundation.phase.relationship_preview"),
    ("literature_evidence", "foundation.phase.literature_evidence"),
    ("research_strategy", "foundation.phase.research_strategy"),
    ("h1", "foundation.phase.h1"),
    ("joint_analysis", "foundation.phase.joint_analysis"),
    ("strategy_modeling", "foundation.phase.strategy_modeling"),
    ("validation_sensitivity", "foundation.phase.validation_sensitivity"),
    ("h2", "foundation.phase.h2"),
    ("paper_latex", "foundation.phase.paper_latex"),
    ("h3", "foundation.phase.h3"),
    ("e2e_acceptance", "foundation.phase.e2e_acceptance"),
)


def mark_project_initialized() -> None:
    """Remember that the user asked to record the current inputs."""
    st.session_state[INITIALIZED_KEY] = True
    st.session_state.pop(SIGNATURE_KEY, None)
    st.session_state[SKIP_NOTICE_KEY] = True


def _resolved_project_id(project_id: str, bundle: DatasetBundle | None) -> str:
    if bundle is not None:
        return bundle.project_id
    return safe_project_id(project_id)


def compute_form_signature(
    *,
    project_id: str,
    project_name: str,
    problem_text: str,
    upload_payloads: list[tuple[str, bytes]],
    bundle: DatasetBundle | None,
    bundle_rejected: bool,
    llm_provider: str,
    llm_model: str,
    llm_config_revision: int,
) -> tuple[str, DatasetBundle | None, str] | None:
    """Return (signature, active_bundle, selection_status) or None if the form is invalid."""
    if bundle is not None and not bundle_rejected:
        active_bundle: DatasetBundle | None = bundle
        selection_status = "ready"
    elif upload_payloads:
        active_bundle = None
        selection_status = "rejected"
    else:
        active_bundle = None
        selection_status = "empty"
    try:
        safe_project_id(project_id) if active_bundle is None else active_bundle.project_id
        token = selection_token(
            upload_payloads,
            fingerprint=active_bundle.fingerprint if active_bundle is not None else None,
            rejected=selection_status == "rejected",
        )
        signature = foundation_input_signature(
            project_id=project_id,
            project_name=project_name,
            problem_text=problem_text,
            selection_token_value=token,
            llm_config_revision=llm_config_revision,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
    except ValueError:
        return None
    return signature, active_bundle, selection_status


def sync_foundation_state(
    *,
    project_id: str,
    project_name: str,
    problem_text: str,
    upload_payloads: list[tuple[str, bytes]],
    bundle: DatasetBundle | None,
    bundle_rejected: bool,
    llm_provider: str,
    llm_model: str,
    llm_config_revision: int,
    store: ProjectStore | None = None,
) -> bool:
    """Store a new foundation state when recorded inputs changed.

    Returns True when the stored state matches the current form. When ``store``
    is provided, the state is also written to Postgres or the local fallback.
    """
    if not st.session_state.get(INITIALIZED_KEY):
        return False
    if len(project_name.strip()) < 3:
        st.error(t("project.name_too_short"))
        st.warning(t("foundation.name_short_warn"))
        return False
    computed = compute_form_signature(
        project_id=project_id,
        project_name=project_name,
        problem_text=problem_text,
        upload_payloads=upload_payloads,
        bundle=bundle,
        bundle_rejected=bundle_rejected,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_config_revision=llm_config_revision,
    )
    if computed is None:
        st.error(t("foundation.id_invalid"))
        st.warning(t("foundation.id_invalid_warn"))
        return False
    signature, active_bundle, selection_status = computed
    resolved_project_id = _resolved_project_id(project_id, active_bundle)

    if st.session_state.get(SIGNATURE_KEY) == signature and "last_run" in st.session_state:
        st.session_state.pop(SKIP_NOTICE_KEY, None)
        return True

    try:
        state = build_initialized_state(
            project_id=resolved_project_id,
            project_name=project_name,
            problem_text=problem_text,
            bundle=active_bundle,
            selection_status=selection_status,
            llm_config_revision=llm_config_revision,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        result = build_foundation_graph().invoke(state)
        if store is not None:
            from app.persistence_panel import persist_foundation_state

            result = persist_foundation_state(
                store,
                project_id=resolved_project_id,
                project_name=project_name,
                state=result,
                input_signature=signature,
            )
        st.session_state["last_run"] = result
        # Derived products were cleared on rebuild; drop orphan UI caches so they
        # cannot outrank the new recorded state (Phase 2 + Phase 3 session keys).
        from app.session_caches import clear_derived_session_caches

        clear_derived_session_caches()
    except (TypeError, ValueError) as exc:
        st.error(str(exc))
        return False

    st.session_state[SIGNATURE_KEY] = signature
    if st.session_state.pop(SKIP_NOTICE_KEY, False):
        return True
    st.info(t("project.inputs_updated"))
    return True


def render_project_phases(state: dict[str, Any] | None, *, inputs_current: bool) -> None:
    """Render the phase board from recorded workspace_phases (no hardcoded lies)."""
    st.subheader(t("foundation.phases_header"))
    st.caption(t("foundation.phases_caption"))
    if state is None:
        phases = {
            "project_initialized": "no",
            "datasets_loaded": "no",
            "independent_eda": "not recorded",
            "relationship_preview": "not recorded",
            "literature_evidence": "not recorded",
            "research_strategy": "not recorded",
            "h1": "not recorded",
            "joint_analysis": NOT_IMPLEMENTED,
            "strategy_modeling": NOT_IMPLEMENTED,
            "validation_sensitivity": "not recorded",
            "h2": "not recorded",
            "paper_latex": "not recorded",
            "h3": "not recorded",
            "e2e_acceptance": "not recorded",
        }
        st.caption(t("foundation.profiles_pending"))
    else:
        phases = dict(state.get("workspace_phases") or {})
        if not inputs_current:
            st.warning(t("foundation.mismatch"))
        metadata = state.get("dataset_metadata") or {}
        if metadata.get("selection_status") == "rejected":
            st.warning(t("foundation.selection_rejected"))
        if phases.get("relationship_preview") == "ready":
            st.caption(t("foundation.relationship_ready"))
    for key, label_key in _PHASE_ROWS:
        value = phases.get(key)
        if value is None:
            # Omit later-stage keys until the run has recorded them, except core rows.
            if key in {
                "project_initialized",
                "datasets_loaded",
                "independent_eda",
                "relationship_preview",
                "joint_analysis",
                "strategy_modeling",
            }:
                value = "unknown"
            else:
                continue
        st.markdown(f"**{t(label_key)}:** {value}")