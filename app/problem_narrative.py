"""Readable problem-intake interpretation, separate from the English schema.

This is a deterministic domain briefing for 2022 MCM C, not a model response or
an assertion of a solved optimal strategy. User-facing locale can change while
the canonical ProblemSpecification stays untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from app.i18n import get_locale


def is_2022_trading_spec(spec: dict[str, Any]) -> bool:
    names = " ".join(
        str(item.get("file_name", "")) for item in spec.get("supplied_datasets", [])
        if isinstance(item, dict)
    ).lower()
    title = str(spec.get("title") or "").lower()
    return ("lbma" in names and "bchain" in names) or (
        "gold" in title and "bitcoin" in title
    )


def trading_research_brief(locale: str = "zh") -> dict[str, Any]:
    """Analytical proposals, not new official problem requirements."""
    if locale == "en":
        return {
            "title": "What the problem actually asks us to solve",
            "thesis": (
                "This is not price forecasting alone. It is a sequential, "
                "transaction-cost-aware portfolio decision problem under a "
                "strict no-future-information constraint."
            ),
            "tasks": [
                ("Decision model", "Define daily cash/gold/Bitcoin holdings and admissible buy/sell/hold actions. "
                 "Report terminal wealth relative to the $1,000 starting cash."),
                ("Reproducible backtest", "Align the Bitcoin calendar with the gold trading calendar; define "
                 "what a decision can know and at what price an order executes."),
                ("Comparative evidence", "Benchmark against hold-cash, gold buy-and-hold, Bitcoin buy-and-hold "
                 "and risk-aware rebalancing; compare terminal return, drawdown and turnover."),
                ("Cost sensitivity", "Perturb the 1% gold and 2% Bitcoin commission assumptions and "
                 "check whether strategy rankings or turnover reverse."),
                ("Deliverables", "Explain results and uncertainty in the report and trader memorandum; "
                 "do not claim an optimum without an appropriate argument."),
            ],
            "models": [
                ("A · Transparent baseline", "Cash hold / single-asset buy-and-hold. "
                 "Reproducible and essential to beat; not an optimized policy.", "Available baseline"),
                ("B · Cost-aware momentum", "Lagged moving-average signal with a no-trade band to account "
                 "for commissions. Must tune only on historical or training windows.", "Research hypothesis"),
                ("C · Risk-aware allocation", "Rolling volatility/covariance estimation with turnover penalties "
                 "and exposure constraints; requires careful causal estimation.", "Research hypothesis"),
                ("D · Dynamic optimization", "Multi-period stochastic/dynamic programming formulation "
                 "with fees and open-market constraints; computationally demanding.", "Research hypothesis"),
            ],
            "risks": [
                "Today's gold PM price cannot be used for an order executed before that quote becomes known.",
                "Gold has market closures; missing gold observations must not imply zero prices or executable trades.",
                "Optimizing and evaluating on the same five-year data risks overfitting.",
                "A high terminal return does not alone establish robustness or global optimality.",
            ],
        }
    return {
        "title": "这道题真正需要解决什么？",
        "thesis": (
            "这不是简单的涨跌预测，而是一个有交易手续费、市场休市约束、"
            "严格禁止未来信息泄漏的序贯资产配置决策问题。"
            "核心目标是建立可执行规则，并证明它优于合理的对照策略。"
        ),
        "tasks": [
            ("每日决策模型", "定义现金、黄金和比特币的持仓状态，以及每天何时买入、卖出、持有；"
             "从 1,000 美元出发计算期末资产价值。"),
            ("可复现历史回测", "按照交易日期对齐两类资产，区分比特币每日交易和黄金休市；"
             "明确当天决策何时获得价格、何时成交，杜绝未来函数。"),
            ("比较与有效性证明", "至少对比持有现金、黄金买入持有、比特币买入持有以及再平衡策略；"
             "同时检查期末收益、最大回撤、交易频率和手续费。"),
            ("手续费敏感性", "分别改变黄金 1% 和比特币 2% 的手续费，观察最优操作方向、"
             "调仓频率及策略优劣是否改变。"),
            ("论文与交易员备忘录", "清楚陈述模型、假设、结果和限制；"
             "若没有严格证明，不能把表现较好的策略称为全局最优。"),
        ],
        "models": [
            ("A · 基线策略", "持有现金、单一资产买入持有。作用是为复杂策略提供最低对照线，"
             "不能当作已优化的结论。", "当前可做基线"),
            ("B · 手续费感知趋势策略", "使用滞后移动平均信号和不交易区间；"
             "仅用历史窗口训练，减少因频繁调仓造成的费用。", "候选研究方向"),
            ("C · 风险控制资产配置", "用历史波动率、协方差估计配置权重，并惩罚换手率；"
             "需要验证模型对高波动时期的稳健性。", "候选研究方向"),
            ("D · 动态规划优化", "将资产持有量、交易费用与交易日历纳入多期决策；"
             "复杂度较高，需要处理状态空间和不确定性。", "候选研究方向"),
        ],
        "risks": [
            "当天黄金 PM 收盘价在公布前不可被用来指导当天更早的成交。",
            "黄金休市日不能交易；缺失报价不能自动视为零价格，也不能向前引用未来报价。",
            "全部历史区间同时调参和评估会带来过拟合。",
            "单纯最大化期末收益不足以证明稳健性，更不能证明全局最优。",
        ],
    }


def render_trading_problem_brief(spec: dict[str, Any]) -> bool:
    """Explain specifically known 2022 C requirements, return whether matched."""
    if not is_2022_trading_spec(spec):
        return False
    zh = get_locale() == "zh"
    d = trading_research_brief("zh" if zh else "en")
    st.markdown(f"### {d['title']}")
    st.write(d["thesis"])
    st.markdown("#### 需要完成的研究任务" if zh else "#### Research work packages")
    for i, (title, body) in enumerate(d["tasks"], start=1):
        with st.container(border=True):
            st.markdown(f"**{i}. {title}**")
            st.write(body)
    st.markdown("#### 初步建模路线（待 EDA 修正）" if zh else "#### Preliminary modeling routes (subject to EDA)")
    for title, body, status in d["models"]:
        st.markdown(f"**{title}** — {status}")
        st.caption(body)
    st.markdown("#### 必须核实的关键风险" if zh else "#### Questions that must be checked")
    for item in d["risks"]:
        st.write(f"• {item}")
    st.info(
        "以上是根据题目给出的研究建议，不是根据真实数据得出的最优策略。"
        "上传数据完成 EDA 后，应重新比较模型，并由独立审查环节提出反例，最后才进入 H1。"
        if zh else
        "These are analytical proposals, not empirical findings. Reassess the "
        "methods after EDA, run an independent critique, then submit to human H1 review."
    )
    return True
