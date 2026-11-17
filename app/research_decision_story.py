"""Human-readable H1 research decision: plan, evidence, modeling route, risks."""
from __future__ import annotations
from typing import Any
import streamlit as st
from app.i18n import get_locale


_METHODS: dict[str, tuple[str,str,str,str,str]] = {
    "trend_following": (
        "趋势规则 / Trend signals",
        "观察过去一段时间的涨跌趋势，而不是预测明天的价格。",
        "算过去 N 天平均价 → 仅在信号满足时买卖 → 交易前先考虑手续费 → 回测是否优于一直持有。",
        "趋势反复反转时会频繁交易，手续费可能吃掉收益。",
        "改变回看天数、交易门槛，并在未参与调参的日期复测。"),
    "portfolio_optimization": (
        "动态资产配置 / Allocation",
        "不把全部资金押在单一资产上，依据过去的风险表现决定仓位。",
        "统计历史波动与两资产关系 → 设黄金、比特币和现金的比例 → 加入交易成本及黄金开市约束。",
        "历史风险关系未必在未来成立，频繁调仓也可能贵。",
        "对照全仓、均分和按风险分配，比较最终价值、最大跌幅及手续费。"),
    "cost_aware_trading": (
        "低频成本控制 / Fee-aware trading",
        "只有预计调整带来的优势足够覆盖手续费才交易。",
        "先定义简单买卖信号 → 算黄金 1%、比特币 2% 的费用 → 设不交易区间 → 检验多种费率。",
        "过宽门槛可能错过机会；门槛靠事后最优选择会过拟合。",
        "比较扣费前后收益、交易次数，改变两种费率重新评估。"),
    "risk_management": (
        "先控制亏损的方案 / Risk controls",
        "优先减少资产大跌时的损失，再评价是否值得牺牲部分收益。",
        "用过去的波动和回撤制定仓位上限 → 大波动时适度减仓 → 对照始终持有。",
        "减仓也可能刚好错过反弹；风控阈值需要样本外检验。",
        "报告账户层面的最大回撤和期末收益，不只看资产价格跌幅。"),
    "simulation_backtest": (
        "基准回测 / Baselines",
        "先算最简单的方法能拿到多少钱，作为复杂方案的对照组。",
        "分别模拟现金不动、黄金买入持有、比特币买入持有 → 按时间更新账户和交易费用。",
        "这能衡量基准，但本身不能证明已找到最优策略。",
        "同一数据、同一手续费和交易日历下比较策略表现。"),
    "mean_reversion": (
        "均值回归 / Mean reversion",
        "研究价格偏离一段时间的平均水平后，会不会逐渐回归。",
        "仅用历史窗口确定均值和偏离程度 → 规定回归信号 → 加入成本和止损约束。",
        "偏离可能继续扩大，不保证一定会回归。",
        "按时间段测试信号持续性、最大亏损和手续费。"),
}
_OTHER = (
    "研究候选方案 / Candidate method",
    "这是一个可供实验检验的研究方向，不是已经验证有效的结果。",
    "先明确输入数据、交易信号、执行时点和手续费，再形成可运行的规则。",
    "当前缺少证明其优于基线的真实实验。",
    "用样本外区间、手续费敏感性和风险指标检验。",
)


def plan_readable(candidate: dict[str, Any], *, language: str = "zh") -> dict[str,str]:
    family = str(candidate.get("method_family") or "")
    title, why, how, risk, test = _METHODS.get(family, _OTHER)
    if language != "zh":
        title = title.split(" / ")[-1]
        why, how, risk, test = {
            "trend_following": (
                "Act on lagged trends rather than claiming to know tomorrow's prices.",
                "Compute past-only moving averages, define buy/sell thresholds, debit fees, backtest.",
                "False signals can cause expensive repeated transactions.",
                "Change window sizes and thresholds on chronological holdouts."),
            "portfolio_optimization": (
                "Diversify cash, gold and Bitcoin using past risk estimates.",
                "Estimate trailing risk, set allocations and enforce fees/market calendars.",
                "Risk correlations and estimates can fail when regimes change.",
                "Compare against single-asset and balanced baselines."),
            "cost_aware_trading": (
                "Trade only when a signal offers enough margin to cover commission.",
                "Define signals, debit gold/Bitcoin fees, test no-trade bands.",
                "High thresholds may miss opportunities; tuned values can overfit.",
                "Compare turnover and net returns across alternative fee levels."),
        }.get(family, (
            "A candidate hypothesis to compare against straightforward baselines.",
            "Make the signal, trade timing, fees and execution explicit.",
            "This is not yet an empirically proven optimum.",
            "Use chronological tests, fee sensitivity and risk metrics.",
        ))
    return {"name":title,"why":why,"how":how,"risk":risk,"test":test}


def render_research_decision(
    proposal: dict[str, Any] | None, eda_report: dict[str, Any] | None,
) -> None:
    zh = get_locale() == "zh"
    if not isinstance(proposal, dict):
        return
    candidates = [x for x in proposal.get("candidates",[]) if isinstance(x,dict)]
    rec_id = proposal.get("recommended_candidate_id")
    recommended = next((c for c in candidates if c.get("candidate_id")==rec_id),None)
    st.markdown("### 先告诉你结论：目前建议研究哪条路线？"
                if zh else "### The decision: what should we test next?")
    if recommended:
        d = plan_readable(recommended, language="zh" if zh else "en")
        st.markdown("**当前优先研究：** "+d["name"] if zh else "**Provisional research priority:** "+d["name"])
        for label,key in (
            (("为什么想到它","Why this candidate"),"why"),
            (("具体应该怎么做","How to implement"),"how"),
            (("这个思路有什么缺点","Weakness"),"risk"),
            (("如何判断它真有用","How to validate"),"test"),
        ):
            st.write(f"**{label[0] if zh else label[1]}：** {d[key]}")
    st.warning(
        "这是“下一步优先测试什么”，不是宣称已经找到收益最高的交易模型。"
        "只有跑通真实数据、和基线公平比较并检验后，才能讨论效果。"
        if zh else
        "A research priority is not a proven optimal strategy. Confirm with real "
        "backtests, comparable baselines, and out-of-sample checks."
    )
    st.markdown("#### 其他路线有什么不同？" if zh else "#### Alternatives worth comparing")
    rows=[]
    for idx,c in enumerate(candidates[:10],1):
        d=plan_readable(c,language="zh" if zh else "en")
        rows.append({
            ("研究方向" if zh else "Approach"):f"{idx}. {d['name']}",
            ("为什么选" if zh else "Purpose"):d["why"],
            ("要验证的风险" if zh else "Main concern"):d["risk"],
            ("优先" if zh else "Priority"):("先试" if zh else "First") if c.get("candidate_id")==rec_id else ("候选" if zh else "Alternative"),
        })
    if rows: st.dataframe(rows,hide_index=True,width="stretch")
    eda=((eda_report or {}).get("interpreted_findings") or {}).get("datasets") or []
    if eda:
        st.markdown("#### 这个建议用了什么数据证据？" if zh else "#### Which observed data informed this?")
        for item in eda[:5]:
            if not isinstance(item,dict): continue
            name=str(item.get("name") or "dataset")
            drawdown=item.get("max_drawdown_pct")
            vol=item.get("volatility_pct")
            if isinstance(vol,(int,float)) and isinstance(drawdown,(int,float)):
                st.write(
                    f"**{name}：** "+ (
                        f"相邻有效报价收益的波动指标 {vol:.2f}%，资产历史最大价格回撤 {drawdown:.1f}%。"
                        "这些是过去数据测出来的事实，只能提示要考虑风险与手续费，无法单独证明哪个模型更好。"
                        if zh else
                        f"Observed quote-return volatility {vol:.2f}%; historical asset-price drawdown {drawdown:.1f}%. These motivate tests, not empirical superiority."
                    )
                )
    st.info(
        "实际实现范围：此版本实验执行器仍只支持有限的确定性基线。"
        "复杂风险配置或动态规划如果尚未实现，不会被标为“已经跑通”。"
        if zh else
        "Implementation boundary: the runner supports limited deterministic baselines. "
        "Advanced allocation/optimization ideas remain unimplemented until tested."
    )
