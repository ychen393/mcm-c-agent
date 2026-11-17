"""Streamlit panel: Research Strategy → Debate/Critic → human H1 gate (Phase 5)."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from app.i18n import get_locale, t
from app.problem_narrative import is_2022_trading_spec, trading_research_brief

from agents.debate_critic import critique_research_proposal
from agents.research_strategy import synthesize_research_proposal
from agents.live_research_team import run_live_research_team
from agents.research_revision import revise_with_feedback
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
    zh = get_locale() == "zh"
    st.markdown(
        "#### Agent 协作流程：从题目和 EDA 走向可验证模型"
        if zh else
        "#### Agent collaboration: from problem and EDA to testable models"
    )
    st.write(
        "① Problem Analyst（题意与约束） → ② EDA Specialist（真实数据证据） → "
        "③ Research Strategist（候选方案） → ④ Debate Critic（反例与风险） → "
        "⑤ 你批准 H1。每个环节都有可见输出，没有自动批准。"
        if zh else
        "Problem Analyst → EDA Specialist → Research Strategist → Debate Critic → "
        "your H1 approval. Each role produces visible outputs; nothing is auto-approved."
    )
    insight = (eda_report or {}).get("interpreted_findings") if isinstance(eda_report, dict) else None
    measured = insight.get("datasets", []) if isinstance(insight, dict) else []
    if measured:
        st.success(
            (f"EDA Agent 已提供 {len(measured)} 份上传数据的统计证据；"
             "候选方案将引用波动率、回撤与缺失值风险。")
            if zh else f"EDA Agent supplied observed statistics for {len(measured)} datasets."
        )
        for observed in measured[:5]:
            st.caption(
                f"{observed.get('name')}: "
                f"volatility={observed.get('volatility_pct')}%, "
                f"drawdown={observed.get('max_drawdown_pct')}%, "
                f"valid quotes={observed.get('valid_prices')}"
            )
    else:
        st.warning(
            "尚无真实 EDA 数值；可以预览备选方案，但不能凭题目直接证明推荐模型更好。"
            if zh else
            "No observed EDA statistics. Candidate ideas may be previewed but not empirically ranked."
        )
    if isinstance(problem_specification, dict) and is_2022_trading_spec(problem_specification):
        brief = trading_research_brief("zh" if zh else "en")
        with st.expander("模型方案比较与实施边界" if zh else "Candidate model families and implementation scope", expanded=True):
            for title, description, status in brief["models"]:
                st.write(f"**{title} · {status}**")
                st.caption(description)
        st.caption(
            "研究假设不等于已经实现。现有执行器只支持有限的确定性基线策略；"
            "应确认所批准的候选方法与实际执行的策略一致。"
            if zh else
            "Research ideas are not implemented models. The runner currently supports limited "
            "deterministic baselines; verify the approved method matches the executed strategy."
        )

    # Offline specialist tools do not use the legacy unimplemented LLM stub.
    # Live AI advice is controlled exclusively by the explicit two-call opt-in.
    use_llm = False

    team_run = st.button(
        ("运行研究协作：策略 Agent → 独立 Critic" if zh
         else "Run research team: Strategist → independent Critic"),
        type="primary",
        key="run_research_team",
    )
    live_review = st.checkbox(
        ("额外调用真实 LLM Strategist + Critic（2 次模型请求，可能产生费用）"
         if zh else
         "Also run live LLM Strategist + Critic (2 paid API requests possible)"),
        value=False,
        key="research_team_live_opt_in",
    )
    st.caption(
        ("默认协作调用两个独立的离线规则模块，无付费请求。"
         "勾选上方选项并点击运行后，才会额外请求已配置模型两次；"
         "LLM 建议仅供审阅，不能自动批准 H1。")
        if zh else
        "Default team = two independent offline modules (no API charges). "
        "Checking opt-in and clicking run adds two live model requests. "
        "LLM advice never approves H1."
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
            "离线规则 Agent：免费；真实 LLM 仅在上方单独勾选后调用。"
            if zh else
            "Offline rule agents: free; real LLM requires explicit opt-in above."
        )

    proposal_dict = resolve_displayed_proposal(recorded_state)
    critique_dict = resolve_displayed_critique(recorded_state)

    # Human review must be actionable, not a dead-end approval status.
    latest_state = st.session_state.get("last_run")
    review_status = (
        (latest_state.get("approval_status") or {}).get("h1")
        if isinstance(latest_state, dict) else None
    )
    review_decision = (
        ((latest_state.get("decision_report") or {}).get("h1") or {})
        if isinstance(latest_state, dict) else {}
    )
    if review_status == "revision_requested" and isinstance(proposal_dict, dict):
        st.markdown(
            "### 修改意见已收到 · 让模型按你的要求重新做"
            if zh else "### Revision requested · Revise with your actual feedback"
        )
        prior_feedback = str(review_decision.get("notes") or "").strip()
        st.write(
            ("**你上次提出：** " if zh else "**Your exact feedback:** ") + prior_feedback
        )
        st.caption(
            "系统不会仅把状态改为“已退回”。勾选后点按钮，将真实调用模型"
            "重新写方案，再调用独立 Critic 挑问题，保留前后版本；"
            "不自动批准，不自动跑交易模型。"
            if zh else
            "No fake revision: opt in below for one actual model revision and a "
            "second independent critique, retaining before/after versions; H1 stays unapproved."
        )
        review_paid = st.checkbox(
            ("我同意用已配置模型重新生成并审查（2 次 API 请求，可能收费）"
             if zh else
             "I approve two configured-model API calls to revise and critique (may cost money)"),
            value=False, key="h1_revision_two_call_consent",
        )
        regenerate = st.button(
            "按反馈重新生成方案 → 重新审查" if zh else
            "Regenerate from feedback → rerun reviewer",
            key="h1_regenerate_from_feedback",
            type="primary",
        )
        if regenerate:
            if not review_paid:
                st.warning(
                    "请先确认是否允许这两次模型请求。离线规则模块无法理解自由文本反馈，"
                    "因此不会假装已经按你的意见重新生成。"
                    if zh else "Consent is required; offline rules cannot rewrite a free-text research request."
                )
            elif len(prior_feedback) < 12:
                st.error("修改意见太短，请在上一轮审批中填写具体要求。" if zh
                         else "Revision feedback must contain at least 12 characters.")
            elif not isinstance(problem_specification, dict) or not measured:
                st.error(
                    "题目规格或上传数据的 EDA 证据缺失，无法安全重新生成。"
                    if zh else "Problem specification or recorded EDA evidence missing."
                )
            else:
                form_sig = input_signature or st.session_state.get("foundation_input_signature")
                if not form_sig or not isinstance(latest_state, dict):
                    st.error(t("common.sig_missing"))
                else:
                    try:
                        with st.spinner("按你的意见修改方案，并交给独立 Agent 审查…" if zh
                                        else "Revising and independently reviewing…"):
                            revised, audit = revise_with_feedback(
                                proposal=proposal_dict,
                                feedback=prior_feedback,
                                problem_specification=problem_specification,
                                eda_report=eda_report,
                                settings=settings,
                                language="zh" if zh else "en",
                            )
                            new_critique = critique_research_proposal(
                                proposal=revised,
                                problem_specification=problem_specification,
                                evidence_report=evidence_report,
                                eda_report=eda_report,
                                use_llm=False,
                                settings=settings,
                            )
                            store = get_or_create_store(lambda: build_project_store(settings))
                            saved = persist_research_proposal_into_state(
                                store,
                                project_id=str(project_id or latest_state.get("project_id") or "mcm-c-demo"),
                                project_name=str(project_name or latest_state.get("project_name") or "MCM C Demo Project"),
                                state=latest_state,
                                input_signature=str(form_sig),
                                proposal=revised,
                                critique=new_critique,
                                review_record=audit,
                                note="h1-feedback-llm-revision",
                            )
                        st.session_state["last_run"] = saved
                        st.session_state[PROPOSAL_SESSION_KEY] = saved.get("research_proposal")
                        st.session_state[CRITIQUE_SESSION_KEY] = (
                            (saved.get("decision_report") or {}).get("critique")
                        )
                        st.session_state.pop("research_live_team_review", None)
                        st.success(
                            "已重新生成，旧版本和你的反馈已保存。H1 仍待你审核。"
                            if zh else "Revised proposal saved with before/after and feedback. H1 remains pending."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(
                            ("重新生成失败：旧方案和退回状态保持不变。"
                             if zh else "Revision failed; the original proposal and review remain unchanged.")
                            + f" {type(exc).__name__}: {exc}"
                        )
        # In review-requested status, the old candidate must not be approved
        # until an actual revised proposal is attached.
        st.info(
            "当前方案仍处于“待修改”状态，请先完成重新生成，或返回修改反馈。"
            if zh else "This proposal remains under requested revision; do not approve the unchanged version."
        )

    if synthesize or team_run:
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
            st.session_state.pop("research_live_team_review", None)
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

    if critique_btn or team_run:
        if not proposal_dict:
            st.warning(t("h1.synth_before_critique"))
        else:
            try:
                critique = critique_research_proposal(
                    proposal=proposal_dict,
                    problem_specification=problem_specification,
                    evidence_report=evidence_report,
                    eda_report=eda_report,
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
                if team_run:
                    st.info(
                        "研究方案 Agent 和独立 Critic 已分别完成分析。"
                        "请阅读方案和批评，保存方案，再手动决定 H1。"
                        if zh else
                        "Strategist and independent Critic finished. Review both, "
                        "attach the proposal and decide H1 manually."
                    )
                if critique.llm_attempted and critique.llm_note:
                    st.info(critique.llm_note)

    # Optional *real* two-call LLM review, never conflated with deterministic agents.
    if team_run and live_review and proposal_dict and critique_dict:
        if not measured:
            st.warning(
                "未检测到可核对的真实 EDA 统计，已跳过付费 LLM 调用。"
                if zh else "No observed EDA statistics: paid model calls skipped."
            )
        elif not isinstance(problem_specification, dict):
            st.warning("No structured problem specification; live review skipped.")
        else:
            try:
                result = run_live_research_team(
                    specification=problem_specification,
                    proposal=proposal_dict,
                    eda_report=eda_report,
                    settings=settings,
                    language="zh" if zh else "en",
                )
                result["proposal_id"] = proposal_dict.get("proposal_id")
                result["eda_fingerprint"] = (insight or {}).get("bundle_fingerprint")
                st.session_state["research_live_team_review"] = result
                st.success(
                    "真实 LLM Strategist 和 Critic 已分别完成调用；输出不自动成为实验结论。"
                    if zh else "Live LLM Strategist and Critic calls completed; advice remains provisional."
                )
            except Exception as exc:
                st.error(
                    ("真实 LLM 协作调用失败；离线研究方案仍可审阅。"
                     if zh else "Live LLM review failed; offline proposal remains usable.")
                    + f" {type(exc).__name__}: {exc}"
                )

    live_result = st.session_state.get("research_live_team_review")
    if (isinstance(live_result, dict) and isinstance(proposal_dict, dict)
            and live_result.get("proposal_id") == proposal_dict.get("proposal_id")
            and live_result.get("eda_fingerprint") ==
                ((insight or {}).get("bundle_fingerprint"))):
        with st.expander(
            "真实 LLM 两角色审议（建议，不是事实验证）"
            if zh else "Live two-role LLM review (advisory, not validated facts)",
            expanded=True,
        ):
            st.caption(f"{live_result.get('provider')} / {live_result.get('model')}")
            st.markdown("**Strategist**")
            st.write(live_result.get("strategist"))
            st.markdown("**Independent Critic**")
            st.write(live_result.get("critic"))
            st.warning(
                "LLM 内容可能含未经核实的推断；需要和 EDA、基线实验及题目逐项核对。"
                if zh else "LLM output is unverified advice; check against EDA, baselines and problem facts."
            )

    # Show the exact human feedback, old/new plan and real independent review.
    decision_for_history = (
        (st.session_state.get("last_run") or {}).get("decision_report") or {}
    )
    revisions = decision_for_history.get("revision_history") or []
    if isinstance(revisions, list) and revisions:
        latest = revisions[-1]
        st.markdown(
            "### 上次退回后，模型到底改了什么？"
            if zh else "### What exactly changed after your feedback?"
        )
        with st.container(border=True):
            st.markdown("**你提出的意见 / Your feedback**")
            st.write(latest.get("feedback") or "")
            st.markdown("**修改前 / Before**")
            st.write(latest.get("before") or "")
            st.markdown("**修改后 / After**")
            st.write(latest.get("after") or "")
            st.markdown("**怎样回应意见 / What changed**")
            st.write(latest.get("changes_made") or "")
            st.markdown("**独立审查指出的问题 / Independent Critic**")
            st.write(latest.get("critic_feedback") or "")
            st.markdown("**还需要验证什么 / Next tests**")
            st.write(latest.get("next_tests") or "")
            st.caption(
                f"模型：{latest.get('provider')} / {latest.get('model')} · "
                "方案更新后 H1 必须重新审批；这些文字不是实验结果。"
                if zh else
                f"Model: {latest.get('provider')} / {latest.get('model')}. "
                "Revisions require renewed H1 approval and are not test results."
            )
        if len(revisions) > 1:
            with st.expander(
                "历史修改轮次 / Earlier review rounds", expanded=False
            ):
                for round_no, entry in enumerate(revisions[:-1], start=1):
                    st.markdown(f"**Round {round_no}**")
                    st.write(entry.get("feedback") or "")
                    st.caption(entry.get("changes_made") or "")

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
        method_explanations_zh = {
            "portfolio_optimization": "通过历史波动与资产权重设计组合，重点核对收益与回撤之间的取舍。必须加入交易费用和黄金开市约束。",
            "trend_following": "使用过去可获得的趋势信号制定交易规则，需要特别防范手续费侵蚀与样本内过拟合。",
            "cost_aware_trading": "把黄金 1% 与比特币 2% 手续费纳入调仓门槛，研究何时不交易反而更有利。",
            "risk_management": "优先控制极端回撤和仓位暴露，不应仅以期末资产金额评价策略。",
            "simulation_backtest": "通过历史复现与基线比较验证候选策略，不应把回测表现直接称为全局最优。",
            "mean_reversion": "研究价格偏离后回归的可能性，须用实际数据验证信号和参数稳定性。",
            "forecasting": "预测必须采用滚动历史窗口，不能使用未来价格或未来训练信息。",
        }
        for cand in candidates:
            with st.expander(
                f"{cand.get('candidate_id')} · {cand.get('title')} · {cand.get('status')}",
                expanded=cand.get("status") == "recommended",
            ):
                if zh:
                    method_note = method_explanations_zh.get(str(cand.get("method_family") or ""))
                    if method_note:
                        st.info("研究方向中文解读（非原文直译）： " + method_note)
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

    st.markdown(
        "### 你来审阅：同意，还是告诉 Agent 哪里需要重做？"
        if zh else "### Your review: approve or tell the agent what to change"
    )
    st.caption(
        "例如：‘建议不要只用移动平均，要考虑比特币大回撤、黄金周末不开盘；"
        "重新比较风险控制策略，给出具体实验设计。’"
        if zh else
        "Example: 'Do not only use moving averages; address Bitcoin drawdowns, "
        "gold closures and design a risk-controlled comparison.'"
    )
    h1_notes = st.text_area(
        "你对当前方案的修改意见（退回修改时必填）" if zh
        else "Your feedback on this plan (required to request revision)",
        value="",
        height=130,
        key="h1_reviewer_notes",
        help="写清楚哪里不满意、希望怎么调整、如何判断改好了。" if zh
        else "Describe what is wrong, what to change and how to verify improvement.",
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
        elif revise_clicked and len(h1_notes.strip()) < 12:
            st.error(
                "请至少写 12 个字的具体修改意见，让模型知道需要改变什么。"
                if zh else "Write at least 12 characters of actionable revision feedback."
            )
        elif approve_clicked and review_status == "revision_requested":
            st.error("上一轮退回尚未重新生成，不能批准旧方案。" if zh
                     else "Regenerate the rejected proposal before approving.")
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
                        "修改意见已记录。返回本阶段顶部，勾选真实模型重跑后，"
                        "可以比较旧版、新版和独立 Critic 的意见。"
                        if zh else
                        "Feedback recorded. At the top of this stage, explicitly "
                        "authorize model rerun to compare the old and revised plan."
                    )
            except Exception as exc:
                st.error(t("h1.decision_failed", err=f"{type(exc).__name__}: {exc}"))

    return proposal_dict
