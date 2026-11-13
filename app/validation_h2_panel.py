"""Streamlit panel: Validation / Sensitivity → human H2 gate (Phase 7).

Shows deterministic sensitivity results linked to Phase 6 experiments.
Human Approve / Request-revision only — H2 is never auto-approved.
Paper / LaTeX stays blocked until H2 is approved.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st
from app.i18n import t

from agents.validation_sensitivity import (
    run_validation_sensitivity,
    validation_sensitivity_status,
)
from app.artifact_viewers import (
    render_approved_banner,
    render_h2_approval_card,
    render_h2_scenario_viewers,
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
    """Prefer recorded validation_report over an orphan session cache."""
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
        return None
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
    st.subheader(t("h2.subheader"))
    status = validation_sensitivity_status(settings)
    st.caption(t("h2.caption"))

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
        st.caption(t("h2.paper_gate", msg=p_gate.message))

    st.caption(
        t(
            "h2.gate_detail",
            live=status["live_trading_apis"],
            auto=status["h2_auto_approve"],
            req=status["requires_experiment_results"],
        )
    )

    use_llm = st.checkbox(
        t("h2.use_llm"),
        value=bool(settings.validation_use_llm),
        help=t("h2.use_llm_help"),
        key="validation_use_llm_ui",
    )
    st.caption(
        t("h2.llm_effective", effective=use_llm, settings=settings.validation_use_llm)
    )

    report_dict = resolve_displayed_validation_report(recorded_state)

    run_disabled = not v_gate.validation_allowed
    run = st.button(
        t("h2.run"),
        type="primary",
        key="run_validation_sensitivity",
        disabled=run_disabled,
        help=t("h2.blocked"),
    )

    if run:
        if not validation_allowed(
            recorded_state if isinstance(recorded_state, dict) else None
        ):
            st.error(t("h2.refused"))
        elif not isinstance(recorded_state, dict):
            st.error(t("h2.init_before"))
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
                st.error(t("h2.gate_blocked", err=exc))
            except Exception as exc:
                st.error(t("h2.failed", err=f"{type(exc).__name__}: {exc}"))
            else:
                report_dict = report.model_dump(mode="json")
                st.session_state[VALIDATION_SESSION_KEY] = report_dict
                st.success(
                    t(
                        "h2.complete",
                        id=report.report_id,
                        n=len(report.scenarios),
                        base=report.baseline_run_id,
                    )
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

        render_h2_scenario_viewers(report_dict)

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
            st.markdown(t("h2.robustness"))
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
            t("h2.attach"),
            key="persist_validation_report",
            disabled=not v_gate.validation_allowed,
            help=t("h2.attach_help"),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error(t("h2.init_before_attach"))
            elif not form_sig:
                st.error(t("common.sig_missing"))
            elif not validation_allowed(recorded):
                st.error(t("h2.attach_refused"))
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
                    st.success(t("h2.attached"))
                except PermissionError as exc:
                    st.error(t("h2.attach_gate_blocked", err=exc))
                except Exception as exc:
                    st.error(t("h2.persist_failed", err=f"{type(exc).__name__}: {exc}"))

    # --- Human H2 gate (never auto) ---
    st.markdown(t("h2.gate_heading"))
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
        st.info(t("h2.need_report"))
        return report_dict

    h2_status = None
    if isinstance(gate_state, dict):
        h2_status = ((gate_state.get("decision_report") or {}).get("h2") or {}).get(
            "status"
        ) or (gate_state.get("approval_status") or {}).get("h2")
    if h2_status == "approved":
        package_label = (
            f"validation {report_dict.get('report_id') or ''} · "
            f"{len(report_dict.get('scenarios') or [])} scenarios"
        ).strip()
        render_approved_banner("H2", package_label)
        render_h2_approval_card(report_dict)
        with st.expander(t("h2.decision_details"), expanded=False):
            st.caption(f"h2_status={h2_status}")
        return report_dict

    st.markdown(t("h2.approval_card"))
    render_h2_approval_card(report_dict)

    h2_notes = st.text_area(
        t("h2.notes"),
        value="",
        height=80,
        key="h2_reviewer_notes",
        help=t("h2.notes_help"),
    )

    approve_col, revise_col = st.columns(2)
    with approve_col:
        approve_clicked = st.button(
            t("h2.approve"),
            type="primary",
            key="h2_approve",
            help=t("h2.approve_help"),
        )
    with revise_col:
        revise_clicked = st.button(
            t("h2.revise"),
            key="h2_request_revision",
            help=t("h2.revise_help"),
        )

    if approve_clicked or revise_clicked:
        recorded = st.session_state.get("last_run")
        form_sig = input_signature or st.session_state.get("foundation_input_signature")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error(t("h2.init_before_decide"))
        elif not form_sig:
            st.error(t("common.sig_missing"))
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
                    render_approved_banner(
                        "H2",
                        f"validation {report_dict.get('report_id') or 'package'}",
                    )
                    st.success(t("h2.approved_msg", allowed=paper_after.paper_allowed))
                else:
                    st.warning(t("h2.revision_msg", reason=paper_after.reason))
            except Exception as exc:
                st.error(t("h2.decision_failed", err=f"{type(exc).__name__}: {exc}"))

    return report_dict
