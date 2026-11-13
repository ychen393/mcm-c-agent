"""Streamlit panel: Research Strategy → Debate/Critic → human H1 gate (Phase 5)."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from agents.debate_critic import critique_research_proposal
from agents.research_strategy import synthesize_research_proposal
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
    st.subheader("Research Strategy → H1")
    st.caption(
        "Synthesizes candidate methods from ProblemSpecification (+ EDA / Evidence when "
        "present), critiques them for contradictions / weak assumptions / evidence gaps, "
        "and requires explicit human Approve or Request-revision. H1 is never auto-approved. "
        "Modeling stays blocked until H1 is approved."
    )

    use_llm = st.checkbox(
        "Attempt LLM synthesis / critique (optional)",
        value=bool(settings.research_strategy_use_llm),
        help=(
            "Default off. Phase 5 LLM path is a non-inventing stub that records "
            "unavailability; deterministic rules remain authoritative."
        ),
        key="research_strategy_use_llm_ui",
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        synthesize = st.button(
            "Synthesize research proposal",
            type="primary",
            key="run_research_strategy",
        )
    with col_b:
        critique_btn = st.button("Run Debate / Critic", key="run_debate_critic")
    with col_c:
        st.caption(
            f"RESEARCH_STRATEGY_USE_LLM={settings.research_strategy_use_llm} · "
            f"UI override use_llm={use_llm}"
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
            st.error(f"Research Strategy failed: {type(exc).__name__}: {exc}")
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
                f"Proposal ready · candidates={len(proposal.candidates)} · "
                f"recommended={proposal.recommended_candidate_id} · "
                f"strategy={proposal.strategy}"
            )
            if proposal.llm_attempted and proposal.llm_note:
                st.info(proposal.llm_note)

    if critique_btn:
        if not proposal_dict:
            st.warning("Synthesize a research proposal before running Debate / Critic.")
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
                st.error(f"Debate / Critic failed: {type(exc).__name__}: {exc}")
            else:
                critique_dict = critique.model_dump(mode="json")
                st.session_state[CRITIQUE_SESSION_KEY] = critique_dict
                st.success(
                    f"Critique ready · findings={len(critique.findings)} · "
                    f"blocking={critique.blocking_count}"
                )
                if critique.llm_attempted and critique.llm_note:
                    st.info(critique.llm_note)

    if proposal_dict:
        candidates = proposal_dict.get("candidates") or []
        st.markdown(
            f"**Proposal:** `{proposal_dict.get('proposal_id')}` · "
            f"**Candidates:** {len(candidates)} · "
            f"**Recommended:** `{proposal_dict.get('recommended_candidate_id')}` · "
            f"**Spec:** {'yes' if proposal_dict.get('problem_specification_present') else 'no'} · "
            f"**EDA:** {'yes' if proposal_dict.get('eda_context_present') else 'no'} · "
            f"**Evidence:** {'yes' if proposal_dict.get('evidence_present') else 'no'}"
        )
        for note in proposal_dict.get("consensus_notes") or []:
            st.write(f"- {note}")
        if proposal_dict.get("open_questions"):
            st.markdown("**Open questions**")
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
                    st.markdown("**Hypotheses**")
                    for hyp in cand["hypotheses"]:
                        st.write(f"- {hyp.get('statement')}")
                if cand.get("data_needs"):
                    st.markdown("**Data needs**")
                    for need in cand["data_needs"]:
                        st.write(
                            f"- {need.get('description')} "
                            f"(satisfied={need.get('satisfied')})"
                        )
                if cand.get("validation_plan"):
                    st.markdown("**Validation plan**")
                    for plan in cand["validation_plan"]:
                        st.write(f"- [{plan.get('method')}] {plan.get('description')}")
                if cand.get("strengths"):
                    st.markdown("**Strengths:** " + "; ".join(cand["strengths"]))
                if cand.get("weaknesses"):
                    st.markdown("**Weaknesses:** " + "; ".join(cand["weaknesses"]))

        attach = st.button(
            "Attach proposal into project state",
            key="persist_research_proposal",
            help=(
                "Stores a sanitized research_proposal via Phase 1 persistence and sets "
                "H1=pending. Does not approve H1 or unlock modeling."
            ),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error("Initialize the project before attaching a research proposal.")
            elif not form_sig:
                st.error("Foundation signature missing; re-initialize the project.")
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
                    st.success(
                        "Proposal attached with H1=pending. "
                        f"modeling_allowed="
                        f"{((saved.get('decision_report') or {}).get('modeling_gate') or {}).get('modeling_allowed')}"
                    )
                except Exception as exc:
                    st.error(f"Persist proposal failed: {type(exc).__name__}: {exc}")

    if critique_dict:
        findings = critique_dict.get("findings") or []
        st.markdown(
            f"**Critique:** `{critique_dict.get('critique_id')}` · "
            f"**Findings:** {len(findings)} · "
            f"**Blocking:** {critique_dict.get('blocking_count', 0)}"
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
            "Attach critique into project state",
            key="persist_debate_critique",
        ):
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error("Initialize the project before attaching critique.")
            elif not form_sig:
                st.error("Foundation signature missing; re-initialize the project.")
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
                    st.success("Critique attached to decision_report / disagreement_log.")
                except Exception as exc:
                    st.error(f"Persist critique failed: {type(exc).__name__}: {exc}")

    # --- Human H1 gate (never auto) ---
    st.markdown("### Human Approval Gate H1")
    # Prefer last_run so a same-click H1 approval is visible in this panel's gate banner.
    latest_run = st.session_state.get("last_run")
    gate_state = latest_run if isinstance(latest_run, dict) else recorded_state
    gate = modeling_gate_status(gate_state if isinstance(gate_state, dict) else None)
    if gate.modeling_allowed:
        st.success(gate.message)
    else:
        st.warning(gate.message)

    if not proposal_dict:
        st.info("Synthesize and review a proposal before H1.")
        return proposal_dict

    candidate_ids = [
        c.get("candidate_id")
        for c in (proposal_dict.get("candidates") or [])
        if c.get("candidate_id")
    ]
    default_idx = 0
    recommended = proposal_dict.get("recommended_candidate_id")
    if recommended in candidate_ids:
        default_idx = candidate_ids.index(recommended)

    selected = st.selectbox(
        "Candidate to approve (required for Approve)",
        options=candidate_ids or ["(none)"],
        index=default_idx if candidate_ids else 0,
        key="h1_selected_candidate",
    )
    h1_notes = st.text_area(
        "H1 reviewer notes",
        value="",
        height=80,
        key="h1_reviewer_notes",
        help="Required context for Approve / Request-revision decisions.",
    )

    approve_col, revise_col = st.columns(2)
    with approve_col:
        approve_clicked = st.button(
            "Approve research plan (H1)",
            type="primary",
            key="h1_approve",
            help="Human-only. Never auto-approved. Unlocks the modeling gate flag only.",
        )
    with revise_col:
        revise_clicked = st.button(
            "Request revision (H1)",
            key="h1_request_revision",
            help="Returns the proposal for revision; modeling remains blocked.",
        )

    if approve_clicked or revise_clicked:
        recorded = st.session_state.get("last_run")
        form_sig = input_signature or st.session_state.get("foundation_input_signature")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error("Initialize the project and attach the proposal before H1.")
        elif not form_sig:
            st.error("Foundation signature missing; re-initialize the project.")
        elif not candidate_ids:
            st.error("Proposal has no candidates to decide on.")
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
                    st.success(
                        "H1 approved by human. "
                        f"modeling_allowed={gate_after.modeling_allowed}. "
                        "Phase 6 Modeling is not started by this action."
                    )
                else:
                    st.warning(
                        "H1 revision requested. Modeling remains blocked. "
                        f"reason={gate_after.reason}"
                    )
            except Exception as exc:
                st.error(f"H1 decision failed: {type(exc).__name__}: {exc}")

    return proposal_dict
