"""Streamlit panel: Validation / Sensitivity → human H2 gate (Phase 7).

Shows deterministic sensitivity results linked to Phase 6 experiments.
Human Approve / Request-revision only — H2 is never auto-approved.
Paper / LaTeX stays blocked until H2 is approved.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from agents.validation_sensitivity import (
    run_validation_sensitivity,
    validation_sensitivity_status,
)
from app.persistence_panel import get_or_create_store
from core.config import Settings
from database.repositories import build_project_store
from tools.validation_persistence import (
    build_h2_decision,
    persist_h2_decision_into_state,
    persist_validation_into_state,
)
from validation.gate import (
    paper_gate_status,
    validation_allowed,
    validation_gate_status,
)

VALIDATION_SESSION_KEY = "validation_sensitivity_draft"


def clear_validation_h2_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop orphan Phase 7 validation / H2 UI caches."""
    state = st.session_state if session_state is None else session_state
    state.pop(VALIDATION_SESSION_KEY, None)


def resolve_displayed_validation_report(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded validation; keep session cache until attach persists it."""
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        existing = recorded_state.get("validation_report")
        if isinstance(existing, dict) and existing:
            return existing
        decision = recorded_state.get("decision_report") or {}
        if isinstance(decision, dict):
            nested = decision.get("validation")
            if isinstance(nested, dict) and nested:
                return nested
    cached = state.get(VALIDATION_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def render_validation_h2_panel(
    *,
    settings: Settings,
    problem_specification: dict[str, Any] | None = None,
    recorded_state: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    input_signature: str | None = None,
) -> dict[str, Any] | None:
    """Render Validation / Sensitivity + human H2 controls."""
    st.subheader("Validation / Sensitivity → H2")
    status = validation_sensitivity_status(settings)
    st.caption(
        "Runs CI-safe deterministic sensitivity on Phase 6 fixture experiment "
        "outputs (perturb costs / lookback / rebalance windows). Requires human "
        "H1 approval and attached experiment results. Optional LLM critique does "
        "not call live models in this slice. H2 is never auto-approved. Paper / "
        "LaTeX stays blocked until H2 is approved."
    )

    v_gate = validation_gate_status(
        recorded_state if isinstance(recorded_state, dict) else None
    )
    if v_gate.validation_allowed:
        st.success(v_gate.message)
    else:
        st.warning(v_gate.message)

    p_gate = paper_gate_status(
        recorded_state if isinstance(recorded_state, dict) else None
    )
    if p_gate.paper_allowed:
        st.info(p_gate.message)
    else:
        st.caption(f"Paper gate: {p_gate.message}")

    st.caption(
        f"prompt={status['prompt_version']} · live_trading_apis={status['live_trading_apis']} · "
        f"h2_auto_approve={status['h2_auto_approve']} · "
        f"requires_experiment_results={status['requires_experiment_results']}"
    )

    use_llm = st.checkbox(
        "Attempt LLM validation critique (optional stub)",
        value=bool(settings.validation_use_llm),
        help=(
            "Default off. Phase 7 LLM path records an unavailable stub note; "
            "deterministic sensitivity remains authoritative."
        ),
        key="validation_use_llm_ui",
    )

    report_dict = resolve_displayed_validation_report(recorded_state)

    run_disabled = not v_gate.validation_allowed
    run = st.button(
        "Run deterministic validation / sensitivity",
        type="primary",
        key="run_validation_sensitivity",
        disabled=run_disabled,
        help=(
            "Blocked until human H1 is approved and Phase 6 experiment results "
            "are available on project state."
        ),
    )

    if run:
        if not validation_allowed(
            recorded_state if isinstance(recorded_state, dict) else None
        ):
            st.error(
                "Validation refused: need H1 approved and available experiment results."
            )
        elif not isinstance(recorded_state, dict):
            st.error("Initialize the project, approve H1, and attach experiments first.")
        else:
            try:
                report = run_validation_sensitivity(
                    state=recorded_state,
                    problem_specification=problem_specification
                    or recorded_state.get("problem_specification"),
                    proposal=recorded_state.get("research_proposal"),
                    use_llm=use_llm,
                    settings=settings,
                )
            except PermissionError as exc:
                st.error(f"Validation gate blocked run: {exc}")
            except Exception as exc:
                st.error(f"Validation failed: {type(exc).__name__}: {exc}")
            else:
                report_dict = report.model_dump(mode="json")
                st.session_state[VALIDATION_SESSION_KEY] = report_dict
                st.success(
                    f"Validation complete · report={report.report_id} · "
                    f"scenarios={len(report.scenarios)} · "
                    f"baseline={report.baseline_run_id}"
                )
                if report.llm_attempted and report.llm_note:
                    st.info(report.llm_note)

    if report_dict:
        scenarios = report_dict.get("scenarios") or []
        st.markdown(
            f"**Report:** `{report_dict.get('report_id')}` · "
            f"**Baseline run:** `{report_dict.get('baseline_run_id')}` · "
            f"**Proposal:** `{report_dict.get('proposal_id')}` · "
            f"**Candidate:** `{report_dict.get('selected_candidate_id')}` · "
            f"**Scenarios:** {len(scenarios)}"
        )

        baseline_metrics = report_dict.get("baseline_metrics") or []
        if baseline_metrics:
            st.markdown("**Baseline metrics**")
            for metric in baseline_metrics:
                st.write(
                    f"- {metric.get('label')}: **{metric.get('value')}** "
                    f"{metric.get('unit') or ''}".rstrip()
                )

        for scn in scenarios:
            with st.expander(
                f"{scn.get('scenario_id')} · {scn.get('label')} · {scn.get('kind')}",
                expanded=False,
            ):
                st.write(scn.get("description") or "")
                for pert in scn.get("perturbations") or []:
                    st.caption(
                        f"perturb {pert.get('target')}: "
                        f"{pert.get('baseline_value')} → {pert.get('scenario_value')}"
                    )
                for delta in scn.get("deltas") or []:
                    rel = delta.get("relative_delta")
                    rel_txt = f" ({rel:+.2%})" if isinstance(rel, (int, float)) else ""
                    st.write(
                        f"- Δ {delta.get('label')}: "
                        f"{delta.get('baseline_value')} → {delta.get('scenario_value')} "
                        f"(abs {delta.get('absolute_delta')}{rel_txt})"
                    )

        notes = report_dict.get("robustness_notes") or []
        if notes:
            st.markdown("**Robustness notes**")
            for note in notes:
                text = f"`{note.get('note_id')}` · {note.get('severity')} · {note.get('summary')}"
                sev = note.get("severity")
                if sev in {"high", "blocking"}:
                    st.warning(text)
                else:
                    st.info(text)

        for note in report_dict.get("analysis_notes") or []:
            st.caption(note)

        attach = st.button(
            "Attach validation report into project state",
            key="persist_validation_report",
            disabled=not v_gate.validation_allowed,
            help=(
                "Stores sanitized validation_report via Phase 1 persistence and sets "
                "H2=pending. Does not approve H2 or unlock Paper / LaTeX."
            ),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error("Initialize the project before attaching validation.")
            elif not form_sig:
                st.error("Foundation signature missing; re-initialize the project.")
            elif not validation_allowed(recorded):
                st.error(
                    "Attach refused: need H1 approved and available experiment results."
                )
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_validation_into_state(
                        store,
                        project_id=str(
                            project_id or recorded.get("project_id") or "mcm-c-demo"
                        ),
                        project_name=str(
                            project_name
                            or recorded.get("project_name")
                            or "MCM C Demo Project"
                        ),
                        state=recorded,
                        input_signature=str(form_sig),
                        report=report_dict,
                    )
                    st.session_state["last_run"] = saved
                    attached = saved.get("validation_report") or report_dict
                    st.session_state[VALIDATION_SESSION_KEY] = attached
                    st.success(
                        "Validation attached with H2=pending. "
                        f"paper_allowed="
                        f"{((saved.get('decision_report') or {}).get('paper_gate') or {}).get('paper_allowed')}"
                    )
                except PermissionError as exc:
                    st.error(f"Validation gate blocked attach: {exc}")
                except Exception as exc:
                    st.error(f"Persist validation failed: {type(exc).__name__}: {exc}")

    # --- Human H2 gate (never auto) ---
    st.markdown("### Human Approval Gate H2")
    gate_state = (
        recorded_state
        if isinstance(recorded_state, dict)
        else st.session_state.get("last_run")
    )
    paper = paper_gate_status(gate_state if isinstance(gate_state, dict) else None)
    if paper.paper_allowed:
        st.success(paper.message)
    else:
        st.warning(paper.message)

    if not report_dict:
        st.info("Run and review validation / sensitivity before H2.")
        return report_dict

    h2_notes = st.text_area(
        "H2 reviewer notes",
        value="",
        height=80,
        key="h2_reviewer_notes",
        help="Required context for Approve / Request-revision decisions.",
    )

    approve_col, revise_col = st.columns(2)
    with approve_col:
        approve_clicked = st.button(
            "Approve validation (H2)",
            type="primary",
            key="h2_approve",
            help="Human-only. Never auto-approved. Unlocks the paper gate flag only.",
        )
    with revise_col:
        revise_clicked = st.button(
            "Request revision (H2)",
            key="h2_request_revision",
            help="Returns validation for revision; Paper / LaTeX remains blocked.",
        )

    if approve_clicked or revise_clicked:
        recorded = st.session_state.get("last_run")
        form_sig = input_signature or st.session_state.get("foundation_input_signature")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error("Initialize the project and attach validation before H2.")
        elif not form_sig:
            st.error("Foundation signature missing; re-initialize the project.")
        else:
            status_value = "approved" if approve_clicked else "revision_requested"
            try:
                store = get_or_create_store(lambda: build_project_store(settings))
                # Ensure validation is on state before decision.
                if not (recorded.get("validation_report") or {}).get("report_id"):
                    recorded = persist_validation_into_state(
                        store,
                        project_id=str(
                            project_id or recorded.get("project_id") or "mcm-c-demo"
                        ),
                        project_name=str(
                            project_name
                            or recorded.get("project_name")
                            or "MCM C Demo Project"
                        ),
                        state=recorded,
                        input_signature=str(form_sig),
                        report=report_dict,
                    )
                decision = build_h2_decision(
                    status=status_value,  # type: ignore[arg-type]
                    report=report_dict,
                    notes=h2_notes or f"Human H2 {status_value}",
                )
                saved = persist_h2_decision_into_state(
                    store,
                    project_id=str(project_id or recorded.get("project_id") or "mcm-c-demo"),
                    project_name=str(
                        project_name or recorded.get("project_name") or "MCM C Demo Project"
                    ),
                    state=recorded,
                    input_signature=str(form_sig),
                    decision=decision,
                )
                st.session_state["last_run"] = saved
                paper_after = paper_gate_status(saved)
                if status_value == "approved":
                    st.success(
                        "H2 approved by human. "
                        f"paper_allowed={paper_after.paper_allowed}. "
                        "Phase 8 Paper / LaTeX is not started by this action."
                    )
                else:
                    st.warning(
                        "H2 revision requested. Paper / LaTeX remains blocked. "
                        f"reason={paper_after.reason}"
                    )
            except Exception as exc:
                st.error(f"H2 decision failed: {type(exc).__name__}: {exc}")

    return report_dict
