"""User-facing research workflow, with no changes to execution or approval gates."""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app.i18n import get_locale
from app.progress_chrome import derive_progress_chrome


@dataclass(frozen=True)
class Stage:
    title: str
    purpose: str
    deliverable: str
    action: str


STAGES = (
    Stage("理解题目", "确认研究问题、目标和比赛约束。", "题目分析与问题规格", "创建项目并检查问题分析"),
    Stage("探索数据", "检查数据质量、趋势和数据集之间的关系。", "独立 EDA 报告与图表", "上传数据并确认分析结果"),
    Stage("制定研究方案", "比较候选方法、证据和未解决的假设。", "建模方案与 H1 人工审批", "审阅推荐方案并明确批准或退回"),
    Stage("运行模型与实验", "执行已批准的模型，记录数据来源和实验结果。", "可复现的模型实验结果", "检查数据来源，再决定是否运行实验"),
    Stage("验证与优化", "比较基准、敏感性和模型风险。", "验证报告与 H2 人工审批", "检查实验结果和敏感性分析"),
    Stage("论文与导出", "组织论证、公式、图表及引用并最终审核。", "论文草稿、H3 审批与导出文件", "审阅论文内容与引用后批准"),
)
EN_STAGES = (
    Stage("Understand the problem", "Identify research questions and constraints.", "Problem specification", "Create the project and review the problem analysis"),
    Stage("Explore data", "Inspect quality, trends and relationships.", "EDA reports and charts", "Upload and inspect the datasets"),
    Stage("Choose a research plan", "Compare methods, evidence and assumptions.", "Research proposal and human H1 decision", "Review and approve or request revisions"),
    Stage("Run modeling experiments", "Run approved models and record input provenance.", "Reproducible experiment report", "Check the input source before running"),
    Stage("Validate and improve", "Compare baselines, sensitivity and risks.", "Validation report and human H2 decision", "Review results and sensitivity"),
    Stage("Write and export", "Prepare the paper, figures and citations.", "Paper draft, H3 approval and export", "Review the paper and citations"),
)
STEP_TO_STAGE = {
    "project": 0, "problem": 0, "eda": 1, "literature": 2,
    "h1": 2, "modeling": 3, "h2": 4, "paper": 5, "export": 5,
}


def stage_index(step: str) -> int:
    return STEP_TO_STAGE.get(step, 0)


def render_research_guide(state: dict | None) -> None:
    """Read-only stage browser. Existing panels remain the execution authority."""
    zh = get_locale() == "zh"
    stages = STAGES if zh else EN_STAGES
    progress = derive_progress_chrome(state)
    active = stage_index(progress.current_step)
    st.subheader("研究路线 · 你现在在哪里？" if zh else "Research roadmap · Where are you?")
    st.caption(
        "六个用户阶段对应九个底层研究节点。查看阶段不会启动模型或批准闸门。"
        if zh else
        "Six user stages map to nine internal research nodes. Browsing does not run models or approve gates."
    )
    with st.sidebar:
        st.markdown("### 研究路线" if zh else "### Research roadmap")
        for i, stage in enumerate(stages):
            marker = "▶" if i == active else ("✓" if i < active else "○")
            st.caption(f"{marker} {i+1}. {stage.title}")

    selected = st.selectbox(
        "查看阶段说明（不会改变研究进度）" if zh else "Explore a stage (does not change progress)",
        options=list(range(len(stages))),
        index=active,
        format_func=lambda i: f"{i+1}. {stages[i].title}" + (
            (" · 当前" if zh else " · Current") if i == active else ""
        ),
        key="guided_stage_preview",
    )
    stage = stages[selected]
    with st.container(border=True):
        st.markdown(f"#### {('第 ' + str(selected+1) + ' 阶段') if zh else ('Stage ' + str(selected+1))} · {stage.title}")
        st.write(f"**{'这一步做什么' if zh else 'Purpose'}：** {stage.purpose}")
        st.write(f"**{'完成后得到' if zh else 'Deliverable'}：** {stage.deliverable}")
        st.info(f"{'下一步建议' if zh else 'Suggested action'}：{stage.action}")
        if selected != active:
            st.caption(
                "这里只是查看说明；真实进度以已保存的研究状态为准。"
                if zh else "This is a preview; recorded research state determines actual progress."
            )
    if active >= 3:
        st.warning(
            "数据来源：当前建模使用合成 fixture，上传的 CSV 不会驱动回测。不得把结果当作真实数据研究结论。"
            if zh else
            "Data provenance: modeling currently uses a synthetic fixture, not uploaded CSV files. "
            "Do not present fixture results as real-data research findings."
        )
    with st.expander("高级信息：内部研究节点与审批" if zh else "Advanced: internal steps and approvals"):
        st.caption(progress.stepper_line)
        st.caption(
            "H1/H2/H3 只能人工批准；本导航不修改状态。"
            if zh else "H1/H2/H3 require human approval; this guide does not mutate state."
        )
