"""Plain-language, evidence-specific explanations for each market EDA figure.

Every 'finding' is computed from the current user's observations. A modeling
idea is labeled as a hypothesis; it is not presented as established causality.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def chart_stories(frame: pd.DataFrame, summary: dict[str, Any], *, language: str = "zh") -> dict[str, dict[str, str]]:
    zh = language == "zh"
    date = summary.get("date_column")
    price = summary.get("price_column")
    if not date or not price:
        return {}
    values = pd.DataFrame({
        "date": pd.to_datetime(frame[date], errors="coerce"),
        "price": pd.to_numeric(frame[price], errors="coerce"),
    }).dropna()
    values = values[values.price > 0].sort_values("date").drop_duplicates("date", keep="last")
    if len(values) < 2:
        return {}
    values = values.set_index("date")
    returns = values.price.pct_change().dropna() * 100
    drawdown = (values.price / values.price.cummax() - 1) * 100
    price_change = (values.price.iloc[-1] / values.price.iloc[0] - 1) * 100
    largest_move = float(returns.abs().max())
    p95 = float(returns.abs().quantile(.95))
    tail_n = int((returns.abs() > 5).sum())
    dd_min = float(drawdown.min())
    dd_day = str(drawdown.idxmin().date())
    rolling = returns.rolling(20, min_periods=20).std().dropna()
    vol_now = float(rolling.iloc[-1]) if not rolling.empty else None
    vol_high = float(rolling.max()) if not rolling.empty else None
    market = "黄金" if "gold" in str(summary.get("name", "")).lower() else "比特币" if any(t in str(summary.get("name", "")).lower() for t in ("bitcoin", "bchain", "btc")) else "该资产"
    market_en = "gold" if market == "黄金" else "Bitcoin" if market == "比特币" else "this asset"
    if zh:
        return {
            "price": {
                "read": "横轴是报价日期，纵轴是每单位资产的美元价格；关注长期方向和明显的急涨急跌。",
                "finding": f"从首个有效报价 {values.price.iloc[0]:,.2f} 到最后一个 {values.price.iloc[-1]:,.2f}，共变化 {price_change:+.1f}%。这只是事后观察到的首尾价格差，不是策略收益。",
                "inspiration": f"建模时先比较“始终持有{market}”的简单方案，再验证动态买卖是否真的在扣费后更好；不能用事后上涨趋势倒推当时买入时机。",
                "test": "下一步要比较持有现金和单资产买入持有，并明确实际成交价格与决策时点。",
            },
            "returns": {
                "read": "每根柱子的高度表示有多少次相邻有效报价的涨跌幅落在这个范围内。看的是大涨大跌是否常发生，而不是价格水平。",
                "finding": f"共 {len(returns)} 次有效报价间隔变化；95% 的绝对涨跌幅不超过约 {p95:.2f}%，最大单次绝对变化为 {largest_move:.2f}%；其中 {tail_n} 次超过 5%。",
                "inspiration": "如果出现明显的极端涨跌，不能只追求平均收益；应把交易次数、手续费、仓位上限和极端行情表现纳入模型。",
                "test": "后续测试成本敏感的趋势策略及极端行情中的持仓表现。注意黄金两次报价之间可能跨周末，不能直接当作每天收益。",
            },
            "drawdown": {
                "read": "零线表示位于截至当天的历史最高价；曲线越低，说明相对之前高点跌得越多。",
                "finding": f"在 {dd_day} 观察到最大历史价格回撤 {dd_min:.1f}%。这衡量资产本身，不代表策略账户实际也会亏这么多。",
                "inspiration": "考虑带有风险控制的仓位上限、减少调仓或止损思路，但必须验证止损是否反而造成反复买卖和更多手续费。",
                "test": "未来同时比较期末资产价值与最大组合回撤；不能只用最终赚了多少作为好坏标准。",
            },
            "rolling": {
                "read": "每个点只使用此前 20 个有效报价间隔的收益，衡量近期涨跌幅是否比过去更不稳定；不是未来预测值。",
                "finding": (
                    f"最新可计算的滚动波动约 {vol_now:.2f}%，历史最高约 {vol_high:.2f}%（均未年化）。"
                    if vol_now is not None else
                    "有效报价间隔不足 20 个，无法可靠画出此项指标；不能据此声称存在低风险或高风险阶段。"
                ),
                "inspiration": "可提出“波动大时降低风险敞口，平稳时恢复”的动态仓位规则；信号只能用过去数据，阈值不可根据未来结果倒推。",
                "test": "采用按时间推进的训练/检验方式，检查动态仓位是否真的降低回撤，而不是仅在已知历史中表现好。",
            },
        }
    return {
        "price": {
            "read": "X: observed quote date; Y: USD per asset unit. Look for broad shifts and abrupt changes.",
            "finding": f"The observed quote changed from {values.price.iloc[0]:,.2f} to {values.price.iloc[-1]:,.2f}, or {price_change:+.1f}%. This is not a strategy return.",
            "inspiration": f"Benchmark buy-and-hold {market_en} first, then test if dynamic trading beats it after fees without using hindsight.",
            "test": "Compare cash-hold and buy-and-hold under explicit information/transaction timing.",
        },
        "returns": {
            "read": "Bars count the changes between consecutive valid quotes. Gold quotes may skip market-closure days.",
            "finding": f"{len(returns)} quote intervals; 95th-percentile absolute move {p95:.2f}%, maximum {largest_move:.2f}%; {tail_n} exceed 5%.",
            "inspiration": "If abrupt moves occur, evaluate tail risk, fees, turnover and position limits, not just mean returns.",
            "test": "Test fee-aware trend rules and adverse episodes; do not equate gold quote intervals with calendar-day Bitcoin returns.",
        },
        "drawdown": {
            "read": "Distance below the past observed price peak; zero marks a new high.",
            "finding": f"Maximum historical asset-price drawdown was {dd_min:.1f}% on {dd_day}; this is NOT portfolio drawdown.",
            "inspiration": "Consider risk budgets/position limits; verify a stop-loss doesn't simply add commission-heavy churn.",
            "test": "Compare strategy terminal wealth AND actual portfolio drawdown.",
        },
        "rolling": {
            "read": "Trailing, nonannualized standard deviation of the last 20 observed quote changes; past data only.",
            "finding": f"Latest {vol_now:.2f}%, historical high {vol_high:.2f}%." if vol_now is not None
                       else "Under 20 valid quote changes: insufficient evidence for rolling volatility.",
            "inspiration": "Hypothesis: vary exposure with past volatility rather than trade a fixed fraction every day.",
            "test": "Use chronological validation to avoid tuning a risk threshold on future market conditions.",
        },
    }


def render_chart_interpretation(story: dict[str, str], *, language: str = "zh") -> None:
    import streamlit as st
    zh = language == "zh"
    parts = [
        ("这张图怎么看", "How to read", "read"),
        ("这份数据实际发现什么", "What THIS data shows", "finding"),
        ("对建模有什么启发", "Modeling inspiration", "inspiration"),
        ("下一步如何验证", "Next check", "test"),
    ]
    for cn, en, key in parts:
        st.write(f"**{cn if zh else en}：** {story[key]}")
