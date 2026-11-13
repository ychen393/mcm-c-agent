"""Streamlit panel: Mathematical Modeling & Experiment (Phase 6).

Configure / run the CI-safe deterministic fixture path, view metrics & artifacts,
and attach results into project state. Refuses to run or persist unless H1 is
approved in ResearchState.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st
from app.i18n import t

from agents.modeling_experiment import (
    modeling_experiment_status,
    run_modeling_experiment,
)
from app.artifact_viewers import (
    render_fixture_vs_uploads_banner,
    render_modeling_artifact_viewers,
)
from app.persistence_panel import get_or_create_store
from core.config import Settings
from database.repositories import build_project_store
from modeling.fixture_data import PRICE_FIXTURE_ID
from modeling.gate import modeling_allowed, modeling_gate_status
from tools.experiment_persistence import persist_experiment_into_state

EXPERIMENT_SESSION_KEY = "modeling_experiment_draft"

STRATEGY_OPTIONS = [
    (t("mod.strategy_auto"), None),
    ("cash_hold", "cash_hold"),
    ("buy_hold_bitcoin", "buy_hold_bitcoin"),
    ("buy_hold_gold", "buy_hold_gold"),
    ("trend_follow_bitcoin", "trend_follow_bitcoin"),
    ("periodic_rebalance_5050", "periodic_rebalance_5050"),
]


def clear_modeling_experiment_cache(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop orphan Phase 6 experiment UI cache."""
    state = st.session_state if session_state is None else session_state
    state.pop(EXPERIMENT_SESSION_KEY, None)


def resolve_displayed_experiment_report(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded decision_report.experiment over an orphan session cache."""
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        decision = recorded_state.get("decision_report") or {}
        if isinstance(decision, dict):
            experiment = decision.get("experiment")
            if isinstance(experiment, dict) and experiment:
                return experiment
        return None
    cached = state.get(EXPERIMENT_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def _candidate_labels(proposal: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not isinstance(proposal, dict):
        return []
    labels: list[tuple[str, str]] = []
    for cand in proposal.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        cid = cand.get("candidate_id")
        if not cid:
            continue
        title = cand.get("title") or cid
        family = cand.get("method_family") or "?"
        labels.append((f"{cid} · {title} · {family}", str(cid)))
    return labels


def render_modeling_experiment_panel(
    *,
    settings: Settings,
    problem_specification: dict[str, Any] | None,
    recorded_state: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    input_signature: str | None = None,
    upload_count: int = 0,
) -> dict[str, Any] | None:
    """Render Modeling & Experiment controls. Returns latest report dict if any."""
    st.subheader(t("mod.subheader"))
    status = modeling_experiment_status(settings)
    st.caption(t("mod.caption"))

    render_fixture_vs_uploads_banner(
        upload_count=int(upload_count or 0),
        fixture_id=PRICE_FIXTURE_ID,
    )

    gate = modeling_gate_status(recorded_state if isinstance(recorded_state, dict) else None)
    if gate.modeling_allowed:
        st.success(gate.message)
    else:
        st.warning(gate.message)

    st.caption(
        f"prompt={status['prompt_version']} · live_trading_apis={status['live_trading_apis']} · "
        f"sandbox_default={status['sandboxed_python_default']} · "
        f"requires_h1_approved={status['requires_h1_approved']}"
    )

    proposal = None
    if isinstance(recorded_state, dict):
        maybe = recorded_state.get("research_proposal")
        if isinstance(maybe, dict) and maybe:
            proposal = maybe

    candidate_choices = _candidate_labels(proposal)
    default_candidate = None
    if isinstance(recorded_state, dict):
        h1 = ((recorded_state.get("decision_report") or {}).get("h1") or {})
        if isinstance(h1, dict):
            default_candidate = h1.get("selected_candidate_id")
    if default_candidate is None and proposal:
        default_candidate = proposal.get("recommended_candidate_id")

    col_cfg_a, col_cfg_b, col_cfg_c = st.columns(3)
    with col_cfg_a:
        if candidate_choices:
            labels = [item[0] for item in candidate_choices]
            ids = [item[1] for item in candidate_choices]
            index = 0
            if default_candidate in ids:
                index = ids.index(default_candidate)
            selected_label = st.selectbox(
                t("mod.candidate"),
                options=labels,
                index=index,
                key="modeling_candidate_select",
            )
            selected_candidate_id = ids[labels.index(selected_label)]
        else:
            selected_candidate_id = None
            st.info(t("mod.need_proposal"))
    with col_cfg_b:
        strategy_labels = [item[0] for item in STRATEGY_OPTIONS]
        strategy_values = [item[1] for item in STRATEGY_OPTIONS]
        strategy_label = st.selectbox(
            t("mod.strategy"),
            options=strategy_labels,
            index=0,
            key="modeling_strategy_select",
        )
        strategy_id = strategy_values[strategy_labels.index(strategy_label)]
    with col_cfg_c:
        lookback = st.number_input(
            t("mod.lookback"),
            min_value=1,
            max_value=10,
            value=3,
            key="modeling_lookback",
        )
        rebalance_every = st.number_input(
            t("mod.rebalance"),
            min_value=1,
            max_value=10,
            value=5,
            key="modeling_rebalance",
        )

    allow_sandbox = st.checkbox(
        t("mod.sandbox"),
        value=bool(settings.modeling_allow_sandboxed_python),
        help=t("mod.sandbox_help"),
        key="modeling_allow_sandbox_ui",
    )

    report_dict = resolve_displayed_experiment_report(recorded_state)

    run_disabled = not gate.modeling_allowed or not proposal or not selected_candidate_id
    run = st.button(
        t("mod.run"),
        type="primary",
        key="run_modeling_experiment",
        disabled=run_disabled,
        help=t("mod.blocked"),
    )

    if run:
        if not modeling_allowed(recorded_state if isinstance(recorded_state, dict) else None):
            st.error(t("mod.refused_h1"))
        elif not isinstance(recorded_state, dict):
            st.error(t("mod.init_before"))
        else:
            try:
                report = run_modeling_experiment(
                    state=recorded_state,
                    problem_specification=problem_specification
                    or recorded_state.get("problem_specification"),
                    proposal=proposal,
                    selected_candidate_id=selected_candidate_id,
                    strategy_id=strategy_id,
                    lookback_days=int(lookback),
                    rebalance_every_n_days=int(rebalance_every),
                    allow_sandboxed_python=allow_sandbox,
                    settings=settings,
                )
            except PermissionError as exc:
                st.error(t("mod.gate_blocked", err=exc))
            except Exception as exc:
                st.error(t("mod.failed", err=f"{type(exc).__name__}: {exc}"))
            else:
                report_dict = report.model_dump(mode="json")
                st.session_state[EXPERIMENT_SESSION_KEY] = report_dict
                st.success(
                    f"Experiment complete · run={report.latest_run_id} · "
                    f"strategy={report.strategy}"
                )
                if report.runs and report.runs[0].sandboxed_python_note:
                    st.info(report.runs[0].sandboxed_python_note)

    if report_dict:
        runs = report_dict.get("runs") or []
        latest = runs[-1] if runs else {}
        st.markdown(
            f"**Report:** `{report_dict.get('report_id')}` · "
            f"**Proposal:** `{report_dict.get('proposal_id')}` · "
            f"**Candidate:** `{report_dict.get('selected_candidate_id')}` · "
            f"**Latest run:** `{report_dict.get('latest_run_id')}`"
        )
        metrics = latest.get("metrics") or []
        if metrics:
            st.markdown(t("mod.metrics"))
            for metric in metrics:
                st.write(
                    f"- {metric.get('label')}: **{metric.get('value')}** "
                    f"{metric.get('unit') or ''}".rstrip()
                )
        constraints = latest.get("constraints") or {}
        if constraints:
            st.markdown(t("mod.constraints"))
            st.write(
                f"- initial_cash={constraints.get('initial_cash')} · "
                f"αgold={constraints.get('alpha_gold')} · "
                f"αbitcoin={constraints.get('alpha_bitcoin')} · "
                f"past_data_only={constraints.get('past_data_only')} · "
                f"assets={constraints.get('assets')} · "
                f"source={constraints.get('source')}"
            )
        artifacts = latest.get("artifacts") or []
        if artifacts:
            fixture_id = PRICE_FIXTURE_ID
            params = latest.get("params") or {}
            if isinstance(params, dict) and params.get("price_fixture_id"):
                fixture_id = str(params["price_fixture_id"])
            else:
                for ref in latest.get("code_refs") or []:
                    if isinstance(ref, dict) and ref.get("kind") == "fixture_id":
                        fixture_id = str(ref.get("value") or fixture_id)
            render_modeling_artifact_viewers(artifacts, fixture_id=fixture_id)
            st.markdown(t("mod.artifacts_raw"))
            for art in artifacts:
                with st.expander(
                    f"{art.get('artifact_id')} · {art.get('kind')}",
                    expanded=False,
                ):
                    st.write(art.get("summary") or "")
                    st.json(art.get("payload") or {})
        code_refs = latest.get("code_refs") or []
        if code_refs:
            st.markdown(t("mod.code_refs"))
            for ref in code_refs:
                st.caption(f"{ref.get('kind')}: `{ref.get('value')}`")
        for note in report_dict.get("analysis_notes") or []:
            st.caption(note)

        attach = st.button(
            t("mod.attach"),
            key="persist_modeling_experiment",
            disabled=not gate.modeling_allowed,
            help=t("mod.attach_help"),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error(t("mod.init_before_attach"))
            elif not form_sig:
                st.error(t("common.sig_missing"))
            elif not modeling_allowed(recorded):
                st.error(t("mod.attach_refused_h1"))
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_experiment_into_state(
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
                    attached = ((saved.get("decision_report") or {}).get("experiment")) or report_dict
                    st.session_state[EXPERIMENT_SESSION_KEY] = attached
                    st.success(
                        "Experiment attached · "
                        f"logs={len(saved.get('experiment_logs') or [])} · "
                        f"artifacts={len(saved.get('model_artifacts') or [])} · "
                        f"phase={((saved.get('workspace_phases') or {}).get('strategy_modeling'))}"
                    )
                except PermissionError as exc:
                    st.error(t("mod.attach_gate_blocked", err=exc))
                except Exception as exc:
                    st.error(t("mod.persist_failed", err=f"{type(exc).__name__}: {exc}"))

    return report_dict
