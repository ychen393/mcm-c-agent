"""User-facing six-stage research guide; presentation only, never changes gates."""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

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
STEP_TO_STAGE = {
    "project": 0, "problem": 0, "eda": 1, "literature": 2,
    "h1": 2, "modeling": 3, "h2": 4, "paper": 5, "export": 5,
}

def stage_index(step: str) -> int:
    return STEP_TO_STAGE.get(step, 0)

def render_research_guide(state: dict | None) -> None:
    """Read-only navigation. The existing panels remain the execution authority."""
    progress = derive_progress_chrome(state)
    active = stage_index(progress.current_step)
    st.subheader("研究路线 · 你现在在哪里？")
    st.caption("六个用户阶段对应原有九个研究节点；这里仅解释进度，不会运行模型或自动批准。")
    with st.sidebar:
        st.markdown("### 研究路线")
        for i, stage in enumerate(STAGES):
            marker = "▶" if i == active else ("✓" if i < active else "○")
            st.caption(f"{marker} {i+1}. {stage.title}")
    selected = st.selectbox(
        "查看阶段说明（不会改变研究进度）",
        options=list(range(len(STAGES))),
        index=active,
        format_func=lambda i: f"{i+1}. {STAGES[i].title}" + (" · 当前" if i == active else ""),
        key="guided_stage_preview",
    )
    stage = STAGES[selected]
    with st.container(border=True):
        st.markdown(f"#### 第 {selected+1} 阶段 · {stage.title}")
        st.write(f"**这一步做什么：** {stage.purpose}")
        st.write(f"**完成后得到：** {stage.deliverable}")
        st.info(f"下一步建议：{stage.action}")
        if selected != active:
            st.caption("当前仅查看说明。实际执行进度由保存的研究状态决定。")
    if active >= 3:
        st.warning(
            "数据来源提醒：当前建模模块使用合成价格 fixture；上传的 CSV "
            "不会驱动这条回测路径。此处的实验不能作为真实赛题数据的建模结论。"
        )
    with st.expander("高级信息：底层研究节点与审批"):
        st.caption(progress.stepper_line)
        st.caption("H1 / H2 / H3 必须人工批准；本导航不修改任何审批或运行状态。")
