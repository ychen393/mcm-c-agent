"""Save / reopen / continue / history UI for Phase 1 persistence."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.lifecycle import RECOMPUTE_PROMPT, distinguish_status
from core.project_store import ProjectStore
from schemas.persistence import REUPLOAD_REQUIRED_MESSAGE

STORE_KEY = "project_store"
STALE_NOTICE_KEY = "persistence_stale_notice"


def get_or_create_store(factory) -> ProjectStore:
    """Keep one store instance in the Streamlit session."""
    store = st.session_state.get(STORE_KEY)
    if store is None:
        store = factory()
        st.session_state[STORE_KEY] = store
    return store


def persist_foundation_state(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    state: dict[str, Any],
    input_signature: str,
    note: str = "",
) -> dict[str, Any]:
    """Write the current foundation state; bump run version on signature change."""
    previous = store.get_project(project_id)
    signature_changed = bool(
        previous and previous.input_signature and previous.input_signature != input_signature
    )
    _project, run, saved = store.save_project_state(
        project_id=project_id,
        project_name=project_name,
        state=state,
        input_signature=input_signature,
        note=note,
    )
    if signature_changed:
        st.session_state[STALE_NOTICE_KEY] = RECOMPUTE_PROMPT
    saved = dict(saved)
    saved["run_id"] = run.run_id
    saved["data_resume"] = "reupload_required"
    return saved


def render_persistence_panel(
    store: ProjectStore,
    *,
    project_id: str,
    project_name: str,
    recorded_state: dict[str, Any] | None,
    input_signature: str | None,
) -> None:
    """Render backend info, lifecycle board, history, and reopen/continue actions."""
    info = store.info()
    st.subheader("Project persistence")
    st.caption(
        f"Backend: **{info.backend}** — {info.detail}"
        + (f" Root: `{info.root}`" if info.root else "")
    )
    if info.backend_changed and info.backend_mismatch_message:
        st.warning(info.backend_mismatch_message)
    st.info(REUPLOAD_REQUIRED_MESSAGE)

    status = distinguish_status(recorded_state)
    st.markdown(f"**Project init:** {status['project_init']}")
    st.markdown(f"**Data analysis:** {status['data_analysis']}")
    st.markdown(f"**Research task:** {status['research_task']}")
    if recorded_state is not None:
        st.markdown(
            f"**Data resume:** `{recorded_state.get('data_resume', 'reupload_required')}` "
            "(provenance only — not a full EDA resume)"
        )

    if st.session_state.pop(STALE_NOTICE_KEY, None):
        st.warning(RECOMPUTE_PROMPT)

    if recorded_state and input_signature and store.mark_stale_if_signature_changed(
        project_id, input_signature
    ):
        st.warning(RECOMPUTE_PROMPT)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Save project now", disabled=recorded_state is None):
            if recorded_state is None or not input_signature:
                st.error("Initialize the project before saving.")
            else:
                saved = persist_foundation_state(
                    store,
                    project_id=project_id,
                    project_name=project_name,
                    state=recorded_state,
                    input_signature=input_signature,
                    note="manual save",
                )
                st.session_state["last_run"] = saved
                st.success(f"Saved run {saved.get('run_id')} (lifecycle={saved.get('lifecycle')}).")
    with col_b:
        if st.button("Reopen active run", disabled=not project_id.strip()):
            loaded = store.load_active_state(project_id)
            if loaded is None:
                st.error("No saved active run for this project ID.")
            else:
                st.session_state["last_run"] = loaded
                st.session_state["foundation_initialized"] = True
                st.session_state.pop("foundation_input_signature", None)
                st.warning(REUPLOAD_REQUIRED_MESSAGE)
                st.success(
                    f"Reopened provenance for run {loaded.get('run_id')}. "
                    "Re-upload matching files before EDA."
                )
                st.rerun()
    with col_c:
        if st.button("Continue active run", disabled=not project_id.strip()):
            loaded = store.continue_run(project_id)
            if loaded is None:
                st.error("Nothing to continue for this project ID.")
            else:
                st.session_state["last_run"] = loaded
                st.session_state["foundation_initialized"] = True
                st.session_state.pop("foundation_input_signature", None)
                st.warning(REUPLOAD_REQUIRED_MESSAGE)
                if any(err.get("code") == "stale_run" for err in loaded.get("errors") or []):
                    st.warning(RECOMPUTE_PROMPT)
                else:
                    st.success(
                        f"Continuing provenance for run {loaded.get('run_id')}. "
                        "Re-upload matching files before EDA."
                    )
                st.rerun()

    history = store.history(project_id) if project_id.strip() else []
    if history:
        st.markdown("**Run history / versions**")
        st.dataframe(
            [
                {
                    "version": entry.version,
                    "run_id": entry.run_id,
                    "status": entry.status,
                    "lifecycle": entry.lifecycle,
                    "datasets": entry.dataset_count,
                    "updated_at": entry.updated_at,
                    "note": entry.note,
                }
                for entry in history
            ],
            use_container_width=True,
            hide_index=True,
        )
        choices = {f"v{entry.version} · {entry.run_id} · {entry.status}": entry.run_id for entry in history}
        selected_label = st.selectbox("View historical run", options=list(choices.keys()))
        if st.button("Load selected history version"):
            run_id = choices[selected_label]
            loaded = store.continue_run(project_id, run_id)
            if loaded is None:
                st.error("Could not load that run.")
            else:
                st.session_state["last_run"] = loaded
                st.session_state["foundation_initialized"] = True
                st.warning(REUPLOAD_REQUIRED_MESSAGE)
                if any(err.get("code") == "stale_run" for err in loaded.get("errors") or []):
                    st.warning(
                        "Loaded a stale historical run. Approvals from that version must not be reused."
                    )
                st.rerun()

    projects = store.list_projects()
    if projects:
        with st.expander("All saved projects", expanded=False):
            st.dataframe(
                [
                    {
                        "project_id": item.project_id,
                        "name": item.project_name,
                        "lifecycle": item.lifecycle,
                        "active_run_id": item.active_run_id,
                        "updated_at": item.updated_at,
                    }
                    for item in projects
                ],
                use_container_width=True,
                hide_index=True,
            )
