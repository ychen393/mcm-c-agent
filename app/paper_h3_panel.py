"""Streamlit panel: Paper Planner / LaTeX / Reviewer → human H3 gate (Phase 8).

Shows deterministic outline, offline .tex/.bib emission, and light reviewer
checklist. Human Approve / Request-revision only — H3 is never auto-approved.
Phase 9 E2E stays blocked until H3 is approved. Paper generation requires H2.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st
from app.i18n import get_locale, t
from agents.paper_revision import revise_paper_with_feedback

from agents.paper_planner import paper_planner_status, run_paper_planner
from app.artifact_viewers import (
    render_approved_banner,
    render_h3_approval_card,
    render_paper_pdf_preview,
)
from app.persistence_panel import get_or_create_store
from core.config import Settings
from database.repositories import build_project_store
from paper.gate import e2e_gate_status, paper_allowed, paper_generation_gate_status
from tools.paper_persistence import (
    build_h3_decision,
    persist_h3_decision_into_state,
    persist_paper_into_state,
)

PAPER_SESSION_KEY = "paper_planner_draft"


def clear_paper_h3_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop orphan Phase 8 paper / H3 UI caches."""
    state = st.session_state if session_state is None else session_state
    state.pop(PAPER_SESSION_KEY, None)


def resolve_displayed_paper_package(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded paper package over an orphan session cache."""
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        decision = recorded_state.get("decision_report") or {}
        if isinstance(decision, dict):
            nested = decision.get("paper")
            if isinstance(nested, dict) and nested:
                return nested
        outline = recorded_state.get("paper_outline")
        if isinstance(outline, dict) and outline:
            # Reconstruct a minimal package view from state fields.
            review = recorded_state.get("review_report") or {}
            latex_source = recorded_state.get("latex_source") or ""
            return {
                "package_id": outline.get("package_id") or outline.get("outline_id"),
                "outline": outline,
                "latex": {
                    "bundle_id": (review or {}).get("latex_bundle_id"),
                    "outline_id": outline.get("outline_id"),
                    "tex_source": latex_source,
                    "bib_source": (review or {}).get("bib_source") or "",
                    "compile_attempted": (review or {}).get("compile_attempted"),
                    "compile_ok": (review or {}).get("compile_ok"),
                    "compile_note": (review or {}).get("compile_note"),
                }
                if latex_source
                else None,
                "review": review if isinstance(review, dict) and review else None,
            }
        return None
    cached = state.get(PAPER_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def render_paper_h3_panel(
    *,
    settings: Settings,
    problem_specification: dict[str, Any] | None = None,
    recorded_state: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    input_signature: str | None = None,
) -> dict[str, Any] | None:
    """Render Paper Planner / LaTeX + human H3 controls."""
    st.subheader(t("h3.subheader"))
    status = paper_planner_status(settings)
    st.caption(t("h3.caption"))

    p_gate = paper_generation_gate_status(
        recorded_state if isinstance(recorded_state, dict) else None
    )
    if p_gate.paper_allowed:
        st.success(p_gate.message)
    else:
        st.warning(p_gate.message)

    e_gate = e2e_gate_status(
        recorded_state if isinstance(recorded_state, dict) else None
    )
    if e_gate.e2e_allowed:
        st.info(e_gate.message)
    else:
        st.caption(t("h3.e2e_gate", msg=e_gate.message))

    st.caption(
        f"prompt={status['prompt_version']} · invented_citations={status['invented_citations']} · "
        f"h3_auto_approve={status['h3_auto_approve']} · "
        f"pdf_compile_required_for_ci={status['pdf_compile_required_for_ci']}"
    )

    zh = get_locale() == "zh"
    use_llm = False
    with st.expander("技术配置 / Technical settings", expanded=False):
        st.caption("常规论文草稿生成是离线流程，真实反馈修订只在用户授权后调用 LLM。"
                   if zh else
                   "Standard paper draft is offline; LLM editorial revision requires separate consent.")
    attempt_pdf = st.checkbox(
        t("h3.attempt_pdf"),
        value=False,
        help=t("h3.attempt_pdf_help"),
        key="paper_attempt_pdf_ui",
    )

    package_dict = resolve_displayed_paper_package(recorded_state)
    saved_state = st.session_state.get("last_run")
    current_state = saved_state if isinstance(saved_state,dict) else recorded_state
    h3_decision = ((current_state or {}).get("decision_report") or {}).get("h3") or {}
    h3_status_current = h3_decision.get("status") or ((current_state or {}).get("approval_status") or {}).get("h3")
    h3_returned = h3_status_current == "revision_requested"

    run_disabled = not p_gate.paper_allowed or h3_returned
    run = st.button(
        t("h3.run"),
        type="primary",
        key="run_paper_planner",
        disabled=run_disabled,
        help=t("h3.blocked"),
    )

    if run:
        if not paper_allowed(
            recorded_state if isinstance(recorded_state, dict) else None
        ):
            st.error(t("h3.refused"))
        elif not isinstance(recorded_state, dict):
            st.error(t("h3.init_before"))
        else:
            try:
                package = run_paper_planner(
                    state=recorded_state,
                    problem_specification=problem_specification
                    or recorded_state.get("problem_specification"),
                    use_llm=use_llm,
                    attempt_pdf_compile=attempt_pdf,
                    settings=settings,
                )
            except PermissionError as exc:
                st.error(t("h3.gate_blocked", err=exc))
            except Exception as exc:
                st.error(t("h3.failed", err=f"{type(exc).__name__}: {exc}"))
            else:
                package_dict = package.model_dump(mode="json")
                st.session_state[PAPER_SESSION_KEY] = package_dict
                outline = package.outline
                st.success(
                    f"Paper package ready · package={package.package_id} · "
                    f"outline={outline.outline_id} · sections={len(outline.sections)} · "
                    f"bib={len(outline.bib_entries)} · "
                    f"review={package.review.overall_status if package.review else 'n/a'}"
                )
                if outline.llm_attempted and outline.llm_note:
                    st.info(outline.llm_note)
                if package.latex and package.latex.compile_attempted:
                    if package.latex.compile_ok:
                        st.success(package.latex.compile_note or t("h3.pdf_compiled"))
                    else:
                        st.warning(
                            package.latex.compile_note
                            or "PDF compile soft-failed (not required for CI)."
                        )

    if package_dict and h3_returned:
        st.markdown("### 按照你的审稿意见重新写论文" if zh
                    else "### Rewrite the paper using your actual review comments")
        feedback = str(h3_decision.get("notes") or "").strip()
        st.write(("**你的原话：** " if zh else "**Your feedback:** ") + feedback)
        st.caption(
            "先由模型实际修改已有章节，再重新生成 LaTeX 和参考文献文件，"
            "运行结构与引用检查，并交给第二个独立 Agent 审查。"
            "不会擅自增加数据、编造实验、添加未经核实的文献。"
            if zh else
            "The model edits actual sections; code rebuilds LaTeX and checks citations "
            "before a second model critiques the revision. It never fabricates experiments or sources."
        )
        consent = st.checkbox(
            "授权两次 LLM API 请求修改论文并独立审查（可能收费）"
            if zh else
            "I authorize two provider-model calls for H3 editing and critique (may incur charges)",
            value=False, key="h3_revision_model_consent",
        )
        rerun = st.button(
            "根据意见重写论文 → 重建 LaTeX → 再审查" if zh
            else "Rewrite paper from feedback → rebuild LaTeX → review",
            key="h3_regenerate_from_feedback", type="primary",
        )
        if rerun:
            if not consent:
                st.warning("请先明确授权这两次模型请求；原论文未被修改。"
                           if zh else "Explicit provider-call consent is required; paper unchanged.")
            elif len(feedback)<12:
                st.error("请先提交至少 12 字的具体修改意见。" if zh
                         else "Original review needs at least 12 characters.")
            elif not isinstance(current_state,dict) or not current_state.get("run_id"):
                st.error(t("h3.init_before_decide"))
            else:
                signature = input_signature or st.session_state.get("foundation_input_signature")
                if not signature:
                    st.error(t("common.sig_missing"))
                else:
                    try:
                        with st.spinner("改写论文、重建 LaTeX、检查证据并进行独立审查…" if zh
                                        else "Rewriting, rebuilding and independently reviewing…"):
                            revised, audit = revise_paper_with_feedback(
                                state=current_state, package=package_dict,
                                feedback=feedback, settings=settings,
                                language="zh" if zh else "en",
                            )
                            store = get_or_create_store(lambda: build_project_store(settings))
                            saved = persist_paper_into_state(
                                store,
                                project_id=str(project_id or current_state.get("project_id") or "mcm-c-demo"),
                                project_name=str(project_name or current_state.get("project_name") or "MCM C Demo Project"),
                                state=current_state,
                                input_signature=str(signature),
                                package=revised,
                                revision_record=audit,
                                note="h3-feedback-paper-revision",
                            )
                        st.session_state["last_run"] = saved
                        st.session_state[PAPER_SESSION_KEY] = (
                            (saved.get("decision_report") or {}).get("paper")
                        )
                        st.success("已生成新版论文、LaTeX 与独立审查记录；H3 仍待你批准。"
                                   if zh else "Revised paper and LaTeX saved; H3 awaits human reapproval.")
                        st.rerun()
                    except Exception as exc:
                        st.error(("论文修改失败，旧版和退回状态保持不变：" if zh else
                                  "Paper revision failed; original package and review untouched: ")
                                 + f"{type(exc).__name__}: {exc}")

    history = (((st.session_state.get("last_run") or {}).get("decision_report") or {})
               .get("h3_revision_history") or [])
    if isinstance(history,list) and history:
        latest=history[-1]
        st.markdown("### 修改前后，论文有什么变化？" if zh
                    else "### Which paper sections actually changed?")
        with st.container(border=True):
            for cn,en,key in [
                ("你的修改意见","Human feedback","feedback"),
                ("原章节","Before","before"),
                ("修改后章节","After","after"),
                ("修改说明","What changed","changes_made"),
                ("独立审查人意见","Independent Critic","critic_feedback"),
            ]:
                st.write(f"**{cn if zh else en}：** {latest.get(key) or ''}")
            st.caption("LaTeX 已重新生成；引用与实验数值不允许虚构；H3 必须再次人工批准。"
                       if zh else "LaTeX regenerated; no invented evidence or automatic H3 approval.")

    if package_dict:
        outline = package_dict.get("outline") or {}
        latex = package_dict.get("latex") or {}
        review = package_dict.get("review") or {}
        st.markdown(
            ("### 论文草稿：" if zh else "### Paper draft: ")
            + str(outline.get("title") or "Untitled")
        )
        st.caption(
            "下面是已生成的正文框架，可以展开每章检查内容。"
            "如果论证不够、文字不清楚或遗漏限制，请在底部写具体意见并退回。"
            if zh else
            "Expand sections to inspect the actual draft; request concrete revisions "
            "when explanations, evidence or limitations are incomplete."
        )
        with st.expander("内部版本标识 / Technical package identifiers",expanded=False):
            st.markdown(
                f"**Package:** `{package_dict.get('package_id')}` · "
                f"**Outline:** `{outline.get('outline_id')}` · "
                f"**Title:** {outline.get('title')} · "
                f"**Sections:** {len(outline.get('sections') or [])} · "
                f"**Bib entries:** {len(outline.get('bib_entries') or [])}"
            )

        if outline.get("strategy") == "deterministic_uploaded_csv":
            st.success("论文草稿已关联真实 CSV 实验与敏感性结果（仍需人工核对论证与参考文献）。")
        else:
            st.warning("本论文大纲基于合成测试数据，只能作为结构示例，不能作为正式竞赛成果。")
        render_paper_pdf_preview(package_dict)

        for n, section in enumerate(outline.get("sections") or [], start=1):
            with st.expander(
                f"{n}. {section.get('title')}",
                expanded=section.get("kind") in {"abstract", "methods"},
            ):
                st.write(section.get("summary") or "")
                if section.get("citation_keys"):
                    st.caption("citations: " + ", ".join(section["citation_keys"]))
                for ref in section.get("artifact_refs") or []:
                    st.caption(f"grounded ← {ref.get('kind')}:{ref.get('ref_id')}")

        gaps = outline.get("citation_gaps") or []
        if gaps:
            st.warning(t("h3.citation_gaps", gaps=", ".join(gaps)))

        bib_entries = outline.get("bib_entries") or []
        if bib_entries:
            st.markdown(t("h3.bibliography"))
            for entry in bib_entries:
                st.write(
                    f"- `{entry.get('citation_key')}` — {entry.get('title')} "
                    f"({entry.get('year') or 'n.d.'})"
                )

        if review:
            st.markdown(
                f"**Reviewer:** `{review.get('overall_status')}` · "
                f"structure_ok={review.get('structure_ok')} · "
                f"citations_ok={review.get('citations_ok')} · "
                f"topic_coverage_ok={review.get('topic_coverage_ok')}"
            )
            for finding in review.get("findings") or []:
                text = (
                    f"`{finding.get('finding_id')}` · {finding.get('category')} · "
                    f"{finding.get('status')} · {finding.get('summary')}"
                )
                if finding.get("status") == "fail":
                    st.error(text)
                elif finding.get("status") == "warn":
                    st.warning(text)
                else:
                    st.info(text)

        if latex and latex.get("tex_source"):
            st.download_button(
                "下载 LaTeX 草稿 / Download .tex",
                data=latex["tex_source"].encode("utf-8"),
                file_name="mcm_c_paper_draft.tex",
                mime="text/plain",
                key="paper_download_tex",
            )
            if latex.get("bib_source"):
                st.download_button(
                    "下载参考文献 / Download .bib",
                    data=latex["bib_source"].encode("utf-8"),
                    file_name="mcm_c_references.bib",
                    mime="text/plain",
                    key="paper_download_bib",
                )
            with st.expander("LaTeX source (.tex)", expanded=False):
                st.code(latex.get("tex_source"), language="latex")
            if latex.get("bib_source"):
                with st.expander("BibTeX source (.bib)", expanded=False):
                    st.code(latex.get("bib_source"), language="bibtex")

        for note in outline.get("analysis_notes") or []:
            st.caption(note)

        attach = st.button(
            t("h3.attach"),
            key="persist_paper_package",
            disabled=not p_gate.paper_allowed or h3_returned,
            help=t("h3.attach_help"),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error(t("h3.init_before_attach"))
            elif not form_sig:
                st.error(t("common.sig_missing"))
            elif not paper_allowed(recorded):
                st.error(t("h3.attach_refused"))
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_paper_into_state(
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
                        package=package_dict,
                    )
                    st.session_state["last_run"] = saved
                    nested = (saved.get("decision_report") or {}).get("paper") or package_dict
                    st.session_state[PAPER_SESSION_KEY] = nested
                    st.success(
                        "Paper package attached with H3=pending. "
                        f"e2e_allowed="
                        f"{((saved.get('decision_report') or {}).get('e2e_gate') or {}).get('e2e_allowed')}"
                    )
                except PermissionError as exc:
                    st.error(t("h3.attach_gate_blocked", err=exc))
                except Exception as exc:
                    st.error(t("h3.persist_failed", err=f"{type(exc).__name__}: {exc}"))

    # --- Human H3 gate (never auto) ---
    st.markdown(t("h3.gate_heading"))
    gate_state = (
        recorded_state
        if isinstance(recorded_state, dict)
        else st.session_state.get("last_run")
    )
    e2e = e2e_gate_status(gate_state if isinstance(gate_state, dict) else None)
    if e2e.e2e_allowed:
        st.success(e2e.message)
    else:
        st.warning(e2e.message)

    if not package_dict:
        st.info(t("h3.need_package"))
        return package_dict

    h3_status = None
    if isinstance(gate_state, dict):
        h3_status = ((gate_state.get("decision_report") or {}).get("h3") or {}).get(
            "status"
        ) or (gate_state.get("approval_status") or {}).get("h3")
    outline_title = str(
        ((package_dict.get("outline") or {}).get("title"))
        or package_dict.get("package_id")
        or "paper package"
    )
    if h3_status == "approved":
        render_approved_banner("H3", outline_title)
        render_h3_approval_card(package_dict)
        with st.expander(t("h3.decision_details"), expanded=False):
            st.caption(f"h3_status={h3_status}")
        return package_dict

    st.markdown(t("h3.approval_card"))
    render_h3_approval_card(package_dict)

    st.markdown("### 论文需要修改什么？" if zh else "### What would make the paper acceptable?")
    st.caption(
        "例如：‘结果章节只有一句话，请用已计算的期末资产价值解释比较结果；"
        "结论必须写清手续费影响和不能证明全局最优的限制。’"
        if zh else
        "Example: 'Rewrite the results section around measured terminal wealth; "
        "explain fee sensitivity and avoid claiming global optimality.'"
    )
    h3_notes = st.text_area(
        "给论文 Agent 的修改意见（退回时必填）" if zh else
        "H3 paper revision feedback (required if returning)",
        value="", height=130, key="h3_reviewer_notes",
        help="指出具体章节、错误或不清楚的论证，并说明想看到什么修改。" if zh
        else "Name sections, weaknesses and required changes.",
    )

    approve_col, revise_col = st.columns(2)
    with approve_col:
        approve_clicked = st.button(
            t("h3.approve"),
            type="primary",
            key="h3_approve",
            help=t("h3.approve_help"),
        )
    with revise_col:
        revise_clicked = st.button(
            t("h3.revise"),
            key="h3_request_revision",
            help=t("h3.revise_help"),
        )

    if approve_clicked or revise_clicked:
        recorded = st.session_state.get("last_run")
        form_sig = input_signature or st.session_state.get("foundation_input_signature")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error(t("h3.init_before_decide"))
        elif not form_sig:
            st.error("Foundation signature missing; re-initialize the project.")
        elif revise_clicked and len(h3_notes.strip())<12:
            st.error("请至少填写 12 字的具体论文修改意见。" if zh
                     else "Provide at least 12 characters of actionable paper feedback.")
        elif approve_clicked and h3_returned:
            st.error("原方案已被退回，必须先重新写论文才能批准。" if zh
                     else "Regenerate the returned paper before approval.")
        else:
            status_value = "approved" if approve_clicked else "revision_requested"
            try:
                store = get_or_create_store(lambda: build_project_store(settings))
                if not (
                    (recorded.get("paper_outline") or {}).get("outline_id")
                    or (recorded.get("decision_report") or {}).get("paper")
                ):
                    recorded = persist_paper_into_state(
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
                        package=package_dict,
                    )
                decision = build_h3_decision(
                    status=status_value,  # type: ignore[arg-type]
                    package=package_dict,
                    notes=h3_notes or f"Human H3 {status_value}",
                )
                saved = persist_h3_decision_into_state(
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
                e2e_after = e2e_gate_status(saved)
                if status_value == "approved":
                    render_approved_banner("H3", outline_title)
                    st.success(
                        "H3 approved by human. "
                        f"e2e_allowed={e2e_after.e2e_allowed}. "
                        "Phase 9 E2E is not started by this action."
                    )
                else:
                    st.warning(
                        "H3 revision requested. Phase 9 E2E remains blocked. "
                        f"reason={e2e_after.reason}"
                    )
            except Exception as exc:
                st.error(t("h3.decision_failed", err=f"{type(exc).__name__}: {exc}"))

    return package_dict
