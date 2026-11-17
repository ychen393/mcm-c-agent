"""Streamlit panel: Validation / Sensitivity → human H2 gate (Phase 7).

Shows deterministic sensitivity results linked to Phase 6 experiments.
Human Approve / Request-revision only — H2 is never auto-approved.
Paper / LaTeX stays blocked until H2 is approved.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st
from app.i18n import get_locale, t
from agents.validation_revision import revise_validation_with_feedback

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
from modeling.uploaded_prices import prepare_uploaded_2022_prices
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
    upload_payloads: list[tuple[str, bytes]] | None = None,
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

    zh = get_locale() == "zh"
    use_llm = False
    with st.expander("技术配置与数据来源 / Validation details", expanded=False):
        st.caption("常规敏感性实验由离线代码计算，无付费 LLM 请求。" if zh
                   else "Standard sensitivity runs use offline computation; no paid LLM calls.")

    report_dict = resolve_displayed_validation_report(recorded_state)
    saved_state = st.session_state.get("last_run")
    current_state = saved_state if isinstance(saved_state, dict) else recorded_state
    h2_decision = ((current_state or {}).get("decision_report") or {}).get("h2") or {}
    h2_status = h2_decision.get("status") or ((current_state or {}).get("approval_status") or {}).get("h2")
    h2_returned = h2_status == "revision_requested"

    baseline_experiment = (
        ((recorded_state or {}).get("decision_report") or {}).get("experiment") or {}
    )
    baseline_real = baseline_experiment.get("strategy") == "deterministic_uploaded_csv"
    prepared = None
    if baseline_real:
        files = {name.casefold(): data for name, data in (upload_payloads or [])}
        if "lbma-gold.csv" not in files or "bchain-mkpru.csv" not in files:
            st.warning(
                "真实数据验证要求重新上传原始 LBMA-GOLD.csv 和 BCHAIN-MKPRU.csv "
                "（项目持久化不保存原始数据字节）。"
            )
        else:
            try:
                prepared = prepare_uploaded_2022_prices(
                    files["lbma-gold.csv"], files["bchain-mkpru.csv"]
                )
            except (ValueError, OSError) as exc:
                st.error(f"历史 CSV 不能用于验证：{exc}")
            else:
                st.info("真实 CSV 敏感性分析：必须与建模阶段的两份文件 SHA-256 完全一致。")
    else:
        st.warning("当前基线是合成测试数据；敏感性分析仅用于演示。")
    run_disabled = (not v_gate.validation_allowed or (baseline_real and prepared is None)
                    or h2_returned)
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
                    price_bars=(list(prepared.bars) if prepared is not None else None),
                    price_sha256=({"gold": prepared.gold_sha256, "bitcoin": prepared.bitcoin_sha256}
                                  if prepared is not None else None),
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

    # Real H2 revision loop: user feedback → bounded LLM test plan → real
    # deterministic recomputation → independent LLM critique → fresh H2.
    if report_dict and h2_returned:
        st.markdown("### 你退回的验证意见，交给 Agent 重新执行" if zh
                    else "### Your validation feedback → genuinely recomputed tests")
        feedback = str(h2_decision.get("notes") or "").strip()
        st.write(("**你的原话：** " if zh else "**Your feedback:** ") + feedback)
        st.caption(
            "先由 LLM 把意见转为可执行的手续费／回看窗口／调仓频率实验，"
            "再由离线回测计算新结果，最后由独立 LLM 审查。"
            "如果要求当前系统不支持的样本外检验，会明确阻止而不伪造结果。"
            if zh else
            "Model proposes executable fee/window tests; deterministic code reruns them "
            "against unchanged data; a separate model critiques actual results. "
            "Unsupported methods fail explicitly."
        )
        consent = st.checkbox(
            "授权两次 LLM API 请求来重跑 H2（可能收费）" if zh else
            "I authorize two provider-model calls for H2 revision (may incur charges)",
            value=False, key="h2_revision_model_consent",
        )
        rerun = st.button(
            "按照反馈重新验证 → 独立审查" if zh else
            "Recompute validation from feedback → independent review",
            key="h2_regenerate_from_feedback", type="primary",
        )
        if rerun:
            if not consent:
                st.warning("请先明确授权模型调用；原验证报告保持不变。" if zh
                           else "Explicit model-call consent required; existing report unchanged.")
            elif len(feedback) < 12:
                st.error("原修改意见过短，请重新填写具体问题。" if zh else
                         "Original review feedback is too short.")
            elif baseline_real and prepared is None:
                st.error("请重新上传与建模阶段 SHA-256 完全相同的两份 CSV。" if zh else
                         "Reupload identical original CSVs before real-data validation.")
            elif not isinstance(current_state,dict) or not current_state.get("run_id"):
                st.error(t("h2.init_before_decide"))
            else:
                signature = input_signature or st.session_state.get("foundation_input_signature")
                if not signature:
                    st.error(t("common.sig_missing"))
                else:
                    try:
                        with st.spinner("生成验证计划、实际运行场景、交由第二个 Agent 审查…" if zh
                                        else "Designing, recomputing and reviewing scenarios…"):
                            revised, audit = revise_validation_with_feedback(
                                state=current_state,
                                feedback=feedback,
                                report=report_dict,
                                settings=settings,
                                price_bars=list(prepared.bars) if prepared is not None else None,
                                price_sha256=(
                                    {"gold":prepared.gold_sha256,"bitcoin":prepared.bitcoin_sha256}
                                    if prepared is not None else None
                                ),
                                language="zh" if zh else "en",
                            )
                            store = get_or_create_store(lambda: build_project_store(settings))
                            saved = persist_validation_into_state(
                                store,
                                project_id=str(project_id or current_state.get("project_id") or "mcm-c-demo"),
                                project_name=str(project_name or current_state.get("project_name") or "MCM C Demo Project"),
                                state=current_state,
                                input_signature=str(signature),
                                report=revised,
                                revision_record=audit,
                                note="h2-feedback-computed-revision",
                            )
                        st.session_state["last_run"] = saved
                        st.session_state[VALIDATION_SESSION_KEY] = saved.get("validation_report")
                        st.success("新场景已完成真实计算，并保存新旧对比；H2 仍待你批准。" if zh
                                   else "New scenarios computed, version diff saved. H2 awaits your decision.")
                        st.rerun()
                    except Exception as exc:
                        st.error(("验证重跑失败，旧报告和审批状态未改变：" if zh
                                  else "Recomputation failed; previous report and review unchanged: ")
                                 + f"{type(exc).__name__}: {exc}")

    history = (((st.session_state.get("last_run") or {}).get("decision_report") or {})
               .get("h2_revision_history") or [])
    if isinstance(history,list) and history:
        latest = history[-1]
        st.markdown("### H2 退回后究竟改了什么？" if zh
                    else "### What changed in the H2 validation?")
        with st.container(border=True):
            for cn,en,key in [
                ("你的修改意见","Your feedback","feedback"),
                ("原验证方案","Original validation","before"),
                ("重新计算结果","Recomputed results","after"),
                ("修改原因","What changed","changes_made"),
                ("独立审查意见","Independent reviewer","critic_feedback"),
            ]:
                st.write(f"**{cn if zh else en}：** {latest.get(key) or ''}")
            st.caption("新指标来自离线执行，LLM 未计算或编造结果；H2 需要重新人工批准。"
                       if zh else "Metrics are recomputed offline. Human H2 approval remains necessary.")

    if report_dict:
        if report_dict.get("strategy") == "deterministic_uploaded_csv":
            st.success("已验证的真实 CSV 敏感性结果（仅限样本内）")
        else:
            st.warning("合成测试数据敏感性结果 / Synthetic fixture validation")
        scenarios = report_dict.get("scenarios") or []
        metrics_by_id = {
            str(metric.get("metric_id")): metric.get("value")
            for metric in report_dict.get("baseline_metrics") or []
            if isinstance(metric, dict)
        }
        st.markdown("### 当前策略已经得到什么结果？" if zh else
                    "### What did the actual baseline achieve?")
        baseline_cols = st.columns(3)
        terminal_value = metrics_by_id.get("m_terminal_value")
        max_dd = metrics_by_id.get("m_max_drawdown")
        fees = metrics_by_id.get("m_cost_paid")
        baseline_cols[0].metric(
            "期末资产" if zh else "Ending portfolio value",
            f"USD {terminal_value:,.2f}" if isinstance(terminal_value,(int,float)) else "–",
        )
        baseline_cols[1].metric(
            "最大组合回撤" if zh else "Portfolio drawdown",
            f"{max_dd*100:.1f}%" if isinstance(max_dd,(int,float)) else "–",
        )
        baseline_cols[2].metric(
            "付出的手续费" if zh else "Transaction fees",
            f"USD {fees:,.2f}" if isinstance(fees,(int,float)) else "–",
        )
        requested = [
            s for s in scenarios if isinstance(s,dict)
            and str(s.get("scenario_id") or "").startswith("scn_feedback_")
        ]
        if requested:
            st.markdown("#### 按你反馈新做的实验" if zh else
                        "#### Newly computed tests from your feedback")
            for scenario in requested:
                tested = next(
                    (m for m in scenario.get("metrics") or []
                     if m.get("metric_id")=="m_terminal_value"), {}
                )
                final = tested.get("value")
                pert = scenario.get("perturbations") or []
                detail = pert[0] if pert else {}
                target = detail.get("target")
                old_value = detail.get("baseline_value")
                new_value = detail.get("scenario_value")
                effect = (
                    final - terminal_value
                    if isinstance(final,(int,float)) and isinstance(terminal_value,(int,float))
                    else None
                )
                st.write(
                    (f"**测试 {target}：{old_value} → {new_value}。** "
                     f"重新计算的最终资产为 USD {final:,.2f}，"
                     f"相对原策略变化 {effect:+,.2f} 美元。" if zh else
                     f"**Test {target}: {old_value} → {new_value}.** "
                     f"Recomputed ending value USD {final:,.2f}, difference {effect:+,.2f} USD.")
                    if effect is not None else
                    f"{target}: {old_value} → {new_value}"
                )
            st.caption("上述变化来自相同历史数据的重新执行，不能直接作为样本外有效性的证明。"
                       if zh else "Recomputed on the same data; not out-of-sample evidence.")
        with st.expander("实验标识与完整技术数据 / Technical experiment metadata", expanded=False):
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
            disabled=not v_gate.validation_allowed or h2_returned,
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

    st.markdown("### 你的验收意见" if zh else "### Your review decision")
    st.caption(
        "例如：‘只把手续费翻倍还不够。请增加比特币 3% 手续费，以及不同回看窗口的对照，"
        "解释结果变化。’" if zh else
        "Example: 'Please add a 3% Bitcoin fee stress case and an alternative "
        "lookback window, then compare resulting portfolio metrics.'"
    )
    h2_notes = st.text_area(
        "给 H2 Agent 的修改意见（退回时必填）" if zh else
        "H2 revision feedback (required when returning this report)",
        value="", height=125, key="h2_reviewer_notes",
        help="说明哪些验证没做够、希望增加什么实验以及怎么判断改善。" if zh
        else "Describe missing tests, desired computed scenarios and acceptance criteria.",
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
        elif revise_clicked and len(h2_notes.strip()) < 12:
            st.error("请填写至少 12 字的具体修改意见。" if zh
                     else "Provide at least 12 characters of actionable feedback.")
        elif approve_clicked and h2_returned:
            st.error("上次退回尚未实际重跑，不能批准原报告。" if zh
                     else "Recompute the returned report before approving.")
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
