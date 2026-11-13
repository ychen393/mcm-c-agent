"""Streamlit panel: Research Strategy → Debate/Critic → human H1 gate (Phase 5)."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from app.i18n import t

from agents.debate_critic import critique_research_proposal
from agents.research_strategy import synthesize_research_proposal
from app.artifact_viewers import (
    candidate_display_label,
    render_approved_banner,
    render_h1_approval_card,
    resolve_h1_selected_candidate,
)
from app.persistence_panel import get_or_create_store
from core.config import Settings
from database.repositories import build_project_store
from modeling.gate import modeling_gate_status
from tools.research_persistence import (
    build_h1_decision,
    persist_critique_into_state,
    persist_h1_decision_into_state,
    persist_research_proposal_into_state,
)

PROPOSAL_SESSION_KEY = "research_proposal_draft"
CRITIQUE_SESSION_KEY = "debate_critique_draft"


def clear_research_h1_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop orphan Phase 5 research / H1 UI caches."""
    state = st.session_state if session_state is None else session_state
    state.pop(PROPOSAL_SESSION_KEY, None)
    state.pop(CRITIQUE_SESSION_KEY, None)


def resolve_displayed_proposal(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded ResearchState over an orphan session cache."""
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        existing = recorded_state.get("research_proposal")
        if isinstance(existing, dict) and existing:
            return existing
        return None
    cached = state.get(PROPOSAL_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def resolve_displayed_critique(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        decision = recorded_state.get("decision_report") or {}
        if isinstance(decision, dict):
            critique = decision.get("critique")
            if isinstance(critique, dict) and critique:
                return critique
        return None
    cached = state.get(CRITIQUE_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def render_research_h1_panel(
    *,
    settings: Settings,
    problem_specification: dict[str, Any] | None,
    eda_plan: dict[str, Any] | None = None,
    eda_report: dict[str, Any] | None = None,
    evidence_report: dict[str, Any] | None = None,
    recorded_state: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    input_signature: str | None = None,
) -> dict[str, Any] | None:
    """Render Research Strategy + Critique + human H1 controls."""
    st.subheader(t("h1.subheader"))
    st.caption(t("h1.caption"))

    use_llm = st.checkbox(
        t("h1.use_llm"),
        value=bool(settings.research_strategy_use_llm),
        help=t("h1.use_llm_help"),
        key="research_strategy_use_llm_ui",
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        synthesize = st.button(
            t("h1.synthesize"),
            type="primary",
            key="run_research_strategy",
        )
    with col_b:
        critique_btn = st.button(t("h1.critique"), key="run_debate_critic")
    with col_c:
        st.caption(
            t(
                "h1.llm_effective",
                effective=use_llm,
                settings=settings.research_strategy_use_llm,
            )
        )

    proposal_dict = resolve_displayed_proposal(recorded_state)
    critique_dict = resolve_displayed_critique(recorded_state)

    if synthesize:
        try:
            proposal = synthesize_research_proposal(
                problem_specification=problem_specification,
                eda_plan=eda_plan,
                eda_report=eda_report,
                evidence_report=evidence_report,
                use_llm=use_llm,
                settings=settings,
            )
        except Exception as exc:
            st.error(t("h1.strategy_failed", err=f"{type(exc).__name__}: {exc}"))
        else:
            proposal_dict = proposal.model_dump(mode="json")
            st.session_state[PROPOSAL_SESSION_KEY] = proposal_dict
            # New proposal invalidates prior critique cache.
            st.session_state.pop(CRITIQUE_SESSION_KEY, None)
            critique_dict = None
            if st.session_state.get("last_run") is not None:
                updated = dict(st.session_state["last_run"])
                updated["research_proposal"] = proposal_dict
                approval = dict(updated.get("approval_status") or {})
                approval["h1"] = "pending"
                updated["approval_status"] = approval
                st.session_state["last_run"] = updated
            st.success(
                t(
                    "h1.proposal_ready",
                    n=len(proposal.candidates),
                    rec=proposal.recommended_candidate_id,
                    strategy=proposal.strategy,
                )
            )
            if proposal.llm_attempted and proposal.llm_note:
                st.info(proposal.llm_note)

    if critique_btn:
        if not proposal_dict:
            st.warning(t("h1.synth_before_critique"))
        else:
            try:
                critique = critique_research_proposal(
                    proposal=proposal_dict,
                    problem_specification=problem_specification,
                    evidence_report=evidence_report,
                    use_llm=use_llm,
                    settings=settings,
                )
            except Exception as exc:
                st.error(t("h1.critique_failed", err=f"{type(exc).__name__}: {exc}"))
            else:
                critique_dict = critique.model_dump(mode="json")
                st.session_state[CRITIQUE_SESSION_KEY] = critique_dict
                st.success(
                    t(
                        "h1.critique_ready",
                        n=len(critique.findings),
                        b=critique.blocking_count,
                    )
                )
                if critique.llm_attempted and critique.llm_note:
                    st.info(critique.llm_note)

    if proposal_dict:
        candidates = proposal_dict.get("candidates") or []
        st.markdown(
            t(
                "h1.proposal_summary",
                id=proposal_dict.get("proposal_id"),
                n=len(candidates),
                rec=proposal_dict.get("recommended_candidate_id"),
                spec=("yes" if proposal_dict.get("problem_specification_present") else "no"),
                eda=("yes" if proposal_dict.get("eda_context_present") else "no"),
                ev=("yes" if proposal_dict.get("evidence_present") else "no"),
            )
        )
        for note in proposal_dict.get("consensus_notes") or []:
            st.write(f"- {note}")
        if proposal_dict.get("open_questions"):
            st.markdown(t("h1.open_questions"))
            for q in proposal_dict["open_questions"]:
                st.warning(q)
        for cand in candidates:
            with st.expander(
                f"{cand.get('candidate_id')} · {cand.get('title')} · {cand.get('status')}",
                expanded=cand.get("status") == "recommended",
            ):
                st.write(cand.get("summary") or "")
                st.caption(
                    f"family={cand.get('method_family')} · "
                    f"evidence_cards={len(cand.get('evidence_card_ids') or [])} · "
                    f"gaps={len(cand.get('evidence_gap_ids') or [])}"
                )
                if cand.get("hypotheses"):
                    st.markdown(t("h1.hypotheses"))
                    for hyp in cand["hypotheses"]:
                        st.write(f"- {hyp.get('statement')}")
                if cand.get("data_needs"):
                    st.markdown(t("h1.data_needs"))
                    for need in cand["data_needs"]:
                        st.write(
                            f"- {need.get('description')} "
                            f"(satisfied={need.get('satisfied')})"
                        )
                if cand.get("validation_plan"):
                    st.markdown(t("h1.validation_plan"))
                    for plan in cand["validation_plan"]:
                        st.write(f"- [{plan.get('method')}] {plan.get('description')}")
                if cand.get("strengths"):
                    st.markdown(t("h1.strengths", text="; ".join(cand["strengths"])))
                if cand.get("weaknesses"):
                    st.markdown(t("h1.weaknesses", text="; ".join(cand["weaknesses"])))

        attach = st.button(
            t("h1.attach_proposal"),
            key="persist_research_proposal",
            help=t("h1.attach_proposal_help"),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error(t("h1.init_before_attach"))
            elif not form_sig:
                st.error(t("common.sig_missing"))
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_research_proposal_into_state(
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
                        proposal=proposal_dict,
                        critique=critique_dict,
                    )
                    st.session_state["last_run"] = saved
                    st.session_state[PROPOSAL_SESSION_KEY] = saved.get("research_proposal")
                    st.success(t("h1.proposal_attached"))
                except Exception as exc:
                    st.error(t("h1.persist_proposal_failed", err=f"{type(exc).__name__}: {exc}"))

    if critique_dict:
        findings = critique_dict.get("findings") or []
        st.markdown(
            t(
                "h1.critique_summary",
                id=critique_dict.get("critique_id"),
                n=len(findings),
                b=critique_dict.get("blocking_count", 0),
            )
        )
        for finding in findings:
            level = finding.get("severity")
            text = (
                f"`{finding.get('finding_id')}` · {finding.get('kind')} · "
                f"{level} · {finding.get('statement')}"
            )
            if level == "blocking":
                st.error(text)
            elif level in {"high", "medium"}:
                st.warning(text)
            else:
                st.info(text)
        if proposal_dict and st.button(
            t("h1.attach_critique"),
            key="persist_debate_critique",
        ):
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error(t("h1.init_before_critique"))
            elif not form_sig:
                st.error(t("common.sig_missing"))
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    # Ensure proposal is present on state.
                    if not (recorded.get("research_proposal") or {}).get("proposal_id"):
                        recorded = persist_research_proposal_into_state(
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
                            proposal=proposal_dict,
                            critique=critique_dict,
                        )
                    else:
                        recorded = persist_critique_into_state(
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
                            critique=critique_dict,
                        )
                    st.session_state["last_run"] = recorded
                    st.session_state[CRITIQUE_SESSION_KEY] = (
                        (recorded.get("decision_report") or {}).get("critique")
                    )
                    st.success(t("h1.critique_attached"))
                except Exception as exc:
                    st.error(t("h1.persist_critique_failed", err=f"{type(exc).__name__}: {exc}"))

    # --- Human H1 gate (never auto) ---
    st.markdown(t("h1.gate_heading"))
    gate_state = recorded_state if isinstance(recorded_state, dict) else st.session_state.get("last_run")
    gate = modeling_gate_status(gate_state if isinstance(gate_state, dict) else None)
    if gate.modeling_allowed:
        st.success(gate.message)
    else:
        st.warning(gate.message)

    if not proposal_dict:
        st.info(t("h1.need_proposal"))
        return proposal_dict

    candidates = [
        c
        for c in (proposal_dict.get("candidates") or [])
        if isinstance(c, dict) and c.get("candidate_id")
    ]
    candidate_ids = [str(c["candidate_id"]) for c in candidates]
    labels_by_id = {
        str(c["candidate_id"]): candidate_display_label(c) for c in candidates
    }
    recommended = proposal_dict.get("recommended_candidate_id")

    h1_status, approved_cand, approved_title = resolve_h1_selected_candidate(
        gate_state if isinstance(gate_state, dict) else None,
        proposal_dict,
    )
    already_approved = h1_status == "approved"

    if already_approved:
        render_approved_banner(
            "H1",
            approved_title or labels_by_id.get(str(recommended), t("viewer.research_plan")),
        )
        render_h1_approval_card(
            candidate=approved_cand
            or next((c for c in candidates if c.get("candidate_id") == recommended), None),
            critique=critique_dict,
            recommended=True,
        )
        with st.expander(t("h1.decision_details"), expanded=False):
            st.caption(
                f"selected_id="
                f"{((gate_state or {}).get('decision_report') or {}).get('h1', {}).get('selected_candidate_id')}"
            )
        return proposal_dict

    # Approval card for the candidate under review (recommended by default).
    preview_id = recommended if recommended in candidate_ids else (
        candidate_ids[0] if candidate_ids else None
    )
    preview_cand = next(
        (c for c in candidates if c.get("candidate_id") == preview_id),
        None,
    )
    st.markdown(t("h1.approval_card"))
    render_h1_approval_card(
        candidate=preview_cand,
        critique=critique_dict,
        recommended=bool(preview_id and preview_id == recommended),
    )

    default_idx = 0
    if recommended in candidate_ids:
        default_idx = candidate_ids.index(recommended)
    label_options = [labels_by_id[cid] for cid in candidate_ids] or [t("viewer.none")]
    selected_label = st.selectbox(
        t("h1.candidate_select"),
        options=label_options,
        index=default_idx if candidate_ids else 0,
        key="h1_selected_candidate",
        help=t("h1.candidate_help"),
    )
    selected = None
    if candidate_ids:
        selected = candidate_ids[label_options.index(selected_label)]
        selected_cand = next(
            (c for c in candidates if c.get("candidate_id") == selected), None
        )
        if selected != preview_id:
            st.markdown(t("h1.selected_card"))
            render_h1_approval_card(
                candidate=selected_cand,
                critique=critique_dict,
                recommended=selected == recommended,
            )

    h1_notes = st.text_area(
        t("h1.notes"),
        value="",
        height=80,
        key="h1_reviewer_notes",
        help=t("h1.notes_help"),
    )

    approve_col, revise_col = st.columns(2)
    with approve_col:
        approve_clicked = st.button(
            t("h1.approve"),
            type="primary",
            key="h1_approve",
            help=t("h1.approve_help"),
        )
    with revise_col:
        revise_clicked = st.button(
            t("h1.revise"),
            key="h1_request_revision",
            help=t("h1.revise_help"),
        )

    if approve_clicked or revise_clicked:
        recorded = st.session_state.get("last_run")
        form_sig = input_signature or st.session_state.get("foundation_input_signature")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error(t("h1.init_before_decide"))
        elif not form_sig:
            st.error(t("common.sig_missing"))
        elif not candidate_ids:
            st.error(t("h1.no_candidates"))
        else:
            status = "approved" if approve_clicked else "revision_requested"
            try:
                store = get_or_create_store(lambda: build_project_store(settings))
                # Ensure proposal is on state before decision.
                if not (recorded.get("research_proposal") or {}).get("proposal_id"):
                    recorded = persist_research_proposal_into_state(
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
                        proposal=proposal_dict,
                        critique=critique_dict,
                    )
                decision = build_h1_decision(
                    status=status,  # type: ignore[arg-type]
                    proposal=proposal_dict,
                    selected_candidate_id=selected if selected in candidate_ids else None,
                    notes=h1_notes or f"Human H1 {status}",
                    critique_id=(critique_dict or {}).get("critique_id"),
                )
                saved = persist_h1_decision_into_state(
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
                gate_after = modeling_gate_status(saved)
                if status == "approved":
                    approved_label = labels_by_id.get(str(selected), str(selected))
                    render_approved_banner("H1", approved_label)
                    st.success(
                        t(
                            "h1.approved_msg",
                            allowed=gate_after.modeling_allowed,
                        )
                    )
                else:
                    st.warning(
                        t("h1.revision_msg", reason=gate_after.reason)
                    )
            except Exception as exc:
                st.error(t("h1.decision_failed", err=f"{type(exc).__name__}: {exc}"))

    return proposal_dict
