"""Show and refresh the foundation state from the current project form.

The state is written when the user initializes the project, and again when
that user changes the project, the problem text, the file selection, or the
API settings revision. It is not written on unrelated clicks such as a join
preview. API keys are never copied into the state.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

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

INIT_MESSAGE = "Project initialized — analysis not started."
UPDATE_MESSAGE = "Project inputs updated — analysis not started. Previous approvals are stale."

INITIALIZED_KEY = "foundation_initialized"
SIGNATURE_KEY = "foundation_input_signature"
SKIP_NOTICE_KEY = "foundation_skip_update_notice"

_PHASE_ROWS = (
    ("project_initialized", "Project initialized"),
    ("datasets_loaded", "Datasets loaded"),
    ("independent_eda", "Independent EDA"),
    ("relationship_preview", "Relationship preview"),
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
        st.error("Project name must contain at least 3 characters.")
        st.warning("Foundation state was not updated because the project name is too short.")
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
        st.error("Project ID is invalid.")
        st.warning("Foundation state was not updated because the project ID is invalid.")
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
    st.info(UPDATE_MESSAGE)
    return True


def render_project_phases(state: dict[str, Any] | None, *, inputs_current: bool) -> None:
    """Render the phase board. Joint analysis is always not implemented."""
    st.subheader("Project phases")
    st.caption(
        "Initialization records the problem and dataset provenance. "
        "It does not study the assets, join the files, or model a trading strategy."
    )
    if state is None:
        phases = {
            "project_initialized": "no",
            "datasets_loaded": "no",
            "independent_eda": "not recorded",
            "relationship_preview": "not recorded",
            "joint_analysis": NOT_IMPLEMENTED,
            "strategy_modeling": NOT_IMPLEMENTED,
        }
        st.caption(
            "Any dataset profiles above stay on this page until you initialize the project "
            "or update its inputs. They are not in the project state yet."
        )
    else:
        phases = dict(state.get("workspace_phases") or {})
        if not inputs_current:
            st.warning("The foundation state does not match the current project inputs.")
        metadata = state.get("dataset_metadata") or {}
        if metadata.get("selection_status") == "rejected":
            st.warning(
                "The current file selection is not recorded. "
                "Fix the files and the project state will update."
            )
        if phases.get("relationship_preview") == "ready":
            st.caption(
                "Relationship preview is available. Nothing is joined until you press "
                "Preview join, and a preview is not written into this state."
            )
    for key, label in _PHASE_ROWS:
        st.markdown(f"**{label}:** {phases.get(key, 'unknown')}")
    st.markdown(f"**Joint analysis / strategy modeling:** {NOT_IMPLEMENTED}")
