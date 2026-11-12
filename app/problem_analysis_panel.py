"""Analyze Problem action.

This panel is not the two-node foundation graph. It asks the Problem Analyst
to read the problem text and dataset metadata, then shows a grounded
specification or an explicit failure. It does not approve H1 or trade.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

from core.config import Settings
from core.project_store import ProjectStore, make_artifact

_REVISION_KEY = "problem_revision_notes"


def _wrapper(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {}
    wrapper = state.get("problem_specification") or {}
    return wrapper if isinstance(wrapper, dict) else {}


def _matches(state: dict[str, Any] | None, foundation_signature: str | None, revision: str) -> bool:
    record = _wrapper(state).get("record") or {}
    if not isinstance(record, dict) or not foundation_signature:
        return False
    return (
        record.get("foundation_signature") == foundation_signature
        and record.get("revision_notes") == revision
    )


def _render_specification(spec: dict[str, Any]) -> None:
    st.markdown(f"**Task intent:** {spec.get('task_intent', '')}")
    st.markdown("**Research questions**")
    for question in spec.get("research_questions") or []:
        st.write(f"- {question.get('text')}")
    st.markdown("**Objectives**")
    for objective in spec.get("objectives") or []:
        st.write(f"- {objective.get('text')}")
    st.markdown("**Required outputs**")
    for output in spec.get("required_outputs") or []:
        st.write(f"- {output.get('name')}: {output.get('description')}")
    st.markdown("**Datasets**")
    datasets = spec.get("datasets") or []
    if not datasets:
        st.caption("No dataset role was cited on this specification.")
    for dataset in datasets:
        columns = ", ".join(dataset.get("column_names") or [])
        st.write(f"- `{dataset.get('file_name')}` ({columns})")
    st.markdown("**Official constraints**")
    official = [item for item in spec.get("constraints") or [] if item.get("kind") == "official"]
    inferred = [item for item in spec.get("constraints") or [] if item.get("kind") == "inferred"]
    if not official:
        st.caption("No official numeric constraint was grounded in the problem text.")
    for item in official:
        value = f" Value: {item['value']}." if item.get("value") else ""
        st.write(f"- {item.get('statement')}{value}")
    if inferred:
        st.markdown("**Inferred notes (not official constraints)**")
        for item in inferred:
            st.write(f"- {item.get('statement')}")
    st.markdown("**Unknowns**")
    unknowns = spec.get("uncertainties") or []
    if not unknowns:
        st.caption("No open uncertainties were recorded.")
    for item in unknowns:
        st.write(f"- {item.get('statement')}")
    st.markdown("**Proposed modeling directions**")
    st.caption("Proposed only — not a confirmed fact. No strategy was executed.")
    for item in spec.get("proposed_modeling_directions") or []:
        st.write(f"- {item.get('summary')}")
    st.caption(
        "Downstream modeling and trades were not performed. "
        f"Mode: {spec.get('generation_mode')}. "
        f"LLM analysis complete: {spec.get('llm_analysis_complete')}."
    )


def _render_record(record: dict[str, Any]) -> None:
    usage = record.get("usage") or {}
    tokens = ""
    if usage:
        tokens = (
            f" Tokens in/out: {usage.get('input_tokens', '—')}/"
            f"{usage.get('output_tokens', '—')}."
        )
    st.caption(
        f"Provider: {record.get('provider') or '—'} · model: {record.get('model') or '—'} · "
        f"prompt: {record.get('prompt_version')} · attempts: {record.get('attempts')} · "
        f"billed calls: {record.get('billed_calls')}."
        f"{tokens} "
        f"Started {record.get('started_at') or '—'} · finished {record.get('finished_at') or '—'}."
    )


def render_problem_analysis_panel(
    state: dict[str, Any] | None,
    *,
    settings: Settings,
    store: ProjectStore,
    project_id: str,
    project_name: str,
    problem_text: str,
    foundation_signature: str | None,
    inputs_current: bool,
) -> None:
    """Show Analyze Problem, the current specification, and the H1 handoff."""
    st.subheader("Problem Analyst")
    st.caption(
        "Analyze Problem reads the problem text and dataset metadata. "
        "The two initialization nodes do not do this, and no trading strategy is run."
    )
    revision = st.text_area(
        "Problem analysis revision notes (optional)",
        key=_REVISION_KEY,
        height=80,
        help="Notes are sent as user comments. They are not official problem facts.",
    )
    files = list((state or {}).get("uploaded_files") or [])
    ready_inputs = bool(
        state
        and inputs_current
        and problem_text.strip()
        and files
        and foundation_signature
        and state.get("run_id")
    )
    if st.button("Analyze Problem", type="primary", disabled=not ready_inputs):
        from agents.problem_analyst import run_problem_analysis
        from app.persistence_panel import persist_foundation_state

        with st.spinner("Analyzing the problem text against the recorded metadata…"):
            outcome = run_problem_analysis(
                state or {},
                settings=settings,
                revision_notes=revision,
                foundation_signature=foundation_signature or "",
            )
        saved = outcome.state
        if not outcome.cache_hit:
            try:
                saved = persist_foundation_state(
                    store,
                    project_id=saved.get("project_id") or project_id,
                    project_name=project_name,
                    state=saved,
                    input_signature=foundation_signature or "",
                    note="problem analyst",
                )
                wrapper = _wrapper(saved)
                spec = wrapper.get("specification")
                if wrapper.get("status") == "ready" and isinstance(spec, dict):
                    payload = json.dumps(spec, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    store.add_artifact(
                        make_artifact(
                            project_id=saved["project_id"],
                            run_id=saved["run_id"],
                            kind="problem_specification",
                            uri=f"state://problem_specification/{spec['specification_id']}",
                            sha256=hashlib.sha256(payload).hexdigest(),
                            label=f"ProblemSpecification v{spec.get('version', 1)}",
                            metadata={
                                "schema_version": spec.get("schema_version"),
                                "specification_id": spec.get("specification_id"),
                                "input_signature": spec.get("input_signature"),
                                "prompt_version": spec.get("prompt_version"),
                                "provider": spec.get("provider"),
                                "model": spec.get("model"),
                                "generation_mode": spec.get("generation_mode"),
                                "llm_analysis_complete": bool(spec.get("llm_analysis_complete")),
                                "version": int(spec.get("version") or 1),
                            },
                        )
                    )
            except (TypeError, ValueError) as exc:
                st.error(f"Problem analysis could not be saved: {exc}")
                return
        st.session_state["last_run"] = saved
        st.rerun()

    if not state or not state.get("run_id"):
        st.info("Initialize the project and record datasets before analyzing the problem.")
        return
    if not ready_inputs:
        st.info("Record a problem statement and validated datasets before analyzing again.")
        return

    wrapper = _wrapper(state)
    current = _matches(state, foundation_signature, revision)
    if wrapper.get("record") and not current:
        st.warning(
            "The previous problem specification does not match the current problem text, "
            "files, project, model settings, or revision notes. "
            "It is hidden until you analyze again."
        )
        return
    if not wrapper.get("status"):
        st.info("Problem analysis has not been run for these inputs.")
        return

    record = wrapper.get("record") or {}
    status = wrapper.get("status")
    if status == "blocked":
        st.warning(
            "No configured model. Problem analysis did not run and is not complete. "
            "Set a provider, model, and API key, then analyze again. Recorded datasets were kept."
        )
        _render_record(record)
        return
    if status == "failed":
        st.error(
            "Problem analysis failed. Recorded datasets were kept. "
            f"Reason: {wrapper.get('reason') or record.get('failure_reason') or 'unknown'}."
        )
        _render_record(record)
        return
    if status != "ready":
        st.error("Problem analysis did not produce a specification.")
        return

    spec = wrapper.get("specification") or {}
    if spec.get("generation_mode") == "offline_fixture" or not spec.get("llm_analysis_complete"):
        st.warning("This specification is not a completed LLM analysis.")
    else:
        st.success(
            "Problem specification is ready. It is evidence-grounded and not a trading strategy."
        )
    _render_specification(spec)
    _render_record(record)
    approvals = state.get("approval_status") or {}
    if any(value == "approved" for value in approvals.values()):
        st.warning(
            "An older approval is stored on this run. "
            "It is not an H1 approval of this specification."
        )
    h1 = wrapper.get("h1_plan_request") or {}
    if h1:
        st.info(h1.get("note") or "H1 was not approved.")
        st.caption("H1 approved: false. Strategy included: false.")
    if st.button("Prepare H1 research plan", disabled=status != "ready"):
        from agents.problem_analyst import apply_h1_plan_request
        from app.persistence_panel import persist_foundation_state

        try:
            requested = apply_h1_plan_request(state)
            saved = persist_foundation_state(
                store,
                project_id=requested.get("project_id") or project_id,
                project_name=project_name,
                state=requested,
                input_signature=foundation_signature or "",
                note="h1 plan request",
            )
        except (TypeError, ValueError) as exc:
            st.error(str(exc))
            return
        st.session_state["last_run"] = saved
        st.rerun()
