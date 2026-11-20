"""Observed-date, in-memory gold × Bitcoin joint EDA for 2022 MCM C.

The person explicitly starts the comparison; no durable joined dataset, future
price fill, synthetic quote, or silent trading recommendation is created.
Only compact, source-fingerprinted aggregate statistics may enter ResearchState.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from app.i18n import get_locale
from tools.dataset_bundle import DatasetBundle


JOINT_EDA_SESSION_KEY = "joint_market_eda_confirmation"
ROLLING_PAIRS = 20


def calculate_joint_market_view(gold: pd.DataFrame, btc: pd.DataFrame) -> pd.DataFrame:
    """Align positive, actually observed gold and BTC quotes by exact Date.

    Index=100 at the first common date. Returns/rolling metrics from this frame
    cover consecutive *common quote intervals*, not consecutive calendar days.
    """
    if not {"Date", "USD (PM)"}.issubset(gold.columns):
        raise ValueError("Gold requires Date and USD (PM)")
    if not {"Date", "Value"}.issubset(btc.columns):
        raise ValueError("Bitcoin requires Date and Value")
    a = gold[["Date", "USD (PM)"]].copy()
    b = btc[["Date", "Value"]].copy()
    a["Date"] = pd.to_datetime(a["Date"], errors="coerce")
    b["Date"] = pd.to_datetime(b["Date"], errors="coerce")
    if a["Date"].isna().any() or b["Date"].isna().any():
        raise ValueError("Both date columns must contain valid dates")
    if a["Date"].duplicated().any() or b["Date"].duplicated().any():
        raise ValueError("Duplicate dates prevent one-to-one comparison")
    a["gold_price"] = pd.to_numeric(a["USD (PM)"], errors="coerce")
    b["bitcoin_price"] = pd.to_numeric(b["Value"], errors="coerce")
    joined = a[["Date", "gold_price"]].merge(
        b[["Date", "bitcoin_price"]], on="Date", how="inner", validate="one_to_one"
    ).sort_values("Date")
    joined = joined.dropna(subset=["gold_price", "bitcoin_price"])
    if joined.empty or (joined[["gold_price", "bitcoin_price"]] <= 0).any().any():
        raise ValueError("Need positive observed quotes for both markets on overlap dates")
    joined["gold_index"] = 100 * joined["gold_price"] / joined["gold_price"].iloc[0]
    joined["bitcoin_index"] = 100 * joined["bitcoin_price"] / joined["bitcoin_price"].iloc[0]
    return joined.set_index("Date")


def _valid_quote_dates(frame: pd.DataFrame, price_column: str) -> set[pd.Timestamp]:
    dates = pd.to_datetime(frame["Date"], errors="coerce")
    prices = pd.to_numeric(frame[price_column], errors="coerce")
    return set(dates[dates.notna() & prices.notna() & (prices > 0)].tolist())


def _finite(value: Any) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def calculate_joint_market_insights(
    gold: pd.DataFrame, btc: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Observed facts only. Return joint chart frame and persistence-safe summary."""
    aligned = calculate_joint_market_view(gold, btc)
    gold_dates = _valid_quote_dates(gold, "USD (PM)")
    btc_dates = _valid_quote_dates(btc, "Value")
    if len(aligned) < 2:
        raise ValueError("At least two common valid quote dates are required for comparison")
    returns = aligned[["gold_price", "bitcoin_price"]].pct_change().iloc[1:] * 100
    returns.columns = ["gold_return_pct", "bitcoin_return_pct"]
    g = returns["gold_return_pct"]
    b = returns["bitcoin_return_pct"]
    n = len(returns)
    corr = _finite(g.corr(b)) if n >= 3 else None
    roll = g.rolling(ROLLING_PAIRS, min_periods=ROLLING_PAIRS).corr(b)
    rolling_valid = roll.dropna()
    draws = aligned[["gold_index", "bitcoin_index"]]
    draws = draws.div(draws.cummax()).sub(1) * 100
    summary = {
        "analysis_type": "observed_common_date_2022_mcm_c",
        "joined": False,  # ephemeral calculation, not a stored merged dataset
        "source": "two_uploaded_price_files",
        "overlap_start": str(aligned.index[0].date()),
        "overlap_end": str(aligned.index[-1].date()),
        "gold_observed_days": len(gold_dates),
        "bitcoin_observed_days": len(btc_dates),
        "common_quote_days": len(aligned),
        "paired_return_intervals": n,
        "bitcoin_only_days": len(btc_dates - gold_dates),
        "gold_only_days": len(gold_dates - btc_dates),
        "gold_missing_quotes": int(pd.to_numeric(gold["USD (PM)"], errors="coerce").isna().sum()),
        "bitcoin_missing_quotes": int(pd.to_numeric(btc["Value"], errors="coerce").isna().sum()),
        "gold_end_index": float(aligned["gold_index"].iloc[-1]),
        "bitcoin_end_index": float(aligned["bitcoin_index"].iloc[-1]),
        "paired_return_correlation": corr,
        "gold_interval_volatility_pct": _finite(g.std(ddof=1)) if n >= 2 else None,
        "bitcoin_interval_volatility_pct": _finite(b.std(ddof=1)) if n >= 2 else None,
        "both_negative_intervals": int(((g < 0) & (b < 0)).sum()),
        "both_negative_pct": float(((g < 0) & (b < 0)).mean() * 100),
        "gold_price_drawdown_pct": float(draws["gold_index"].min()),
        "bitcoin_price_drawdown_pct": float(draws["bitcoin_index"].min()),
        "rolling_window_pairs": ROLLING_PAIRS,
        "rolling_corr_latest": _finite(rolling_valid.iloc[-1]) if not rolling_valid.empty else None,
        "rolling_corr_min": _finite(rolling_valid.min()) if not rolling_valid.empty else None,
        "rolling_corr_max": _finite(rolling_valid.max()) if not rolling_valid.empty else None,
        "interpretation_scope": (
            "All paired returns and correlations are measured over adjacent common "
            "quote dates; historical full-window EDA is not a trading signal."
        ),
    }
    return aligned, summary


def joint_chart_explanations(summary: dict[str, Any], language: str = "zh") -> list[dict[str, str]]:
    """Numerical observations → implications → experiments, never predictions."""
    zh = language == "zh"
    corr = summary["paired_return_correlation"]
    n = summary["paired_return_intervals"]
    co_down = summary["both_negative_intervals"]
    rate = summary["both_negative_pct"]
    btc_only = summary["bitcoin_only_days"]
    gd = summary["gold_price_drawdown_pct"]
    bd = summary["bitcoin_price_drawdown_pct"]
    roll_min = summary["rolling_corr_min"]
    roll_max = summary["rolling_corr_max"]
    if zh:
        return [
            {
                "title": "图 1｜两种资产放在同一尺度上，谁涨跌更多？",
                "read": "起点都设为 100；曲线只用两边都有真实价格的日期。100 不是美元，也不是账户余额。",
                "finding": (
                    f"在 {summary['common_quote_days']} 个共同报价日里，两条价格指数从 100 分别到达："
                    f"黄金 {summary['gold_end_index']:.1f}、比特币 {summary['bitcoin_end_index']:.1f}。"
                ),
                "idea": "先用现金不动、单买黄金、单买比特币作公平基线，再判断多资产调仓能否改善扣费后结果。",
                "next": "按题目交易日和手续费进行真实回测；绝不能因为已知终点就事后选择赢家。",
            },
            {
                "title": "图 2｜相同观察区间内，谁波动得更剧烈？",
                "read": "每个点是上一个共同报价日至当前共同报价日的涨跌百分比，可能跨周末，不等于自然日收益。",
                "finding": (
                    f"使用 {n} 段共同报价间隔，黄金和比特币涨跌幅标准差分别约 "
                    f"{summary['gold_interval_volatility_pct']:.2f}%、"
                    f"{summary['bitcoin_interval_volatility_pct']:.2f}%。"
                    if summary["gold_interval_volatility_pct"] is not None else
                    f"只有 {n} 段有效变化，不能可靠估计区间波动差异。"
                ),
                "idea": "如果两者短期波动差异明显，应测试不同仓位上限、风险预算和手续费感知的少调仓策略。",
                "next": "在相同历史区间比较组合回撤、收益、交易次数与费用，不按不同交易日直接比较。",
            },
            {
                "title": "图 3｜黄金和比特币经常一起涨跌吗？",
                "read": "每个点对应两者同一段共同报价间隔的收益；点越沿左下→右上排布，同方向变化越明显。",
                "finding": (
                    f"这 {n} 段的历史收益相关系数为 {corr:+.2f}；"
                    f"两者同时下跌 {co_down} 段（占 {rate:.1f}%）。"
                    if corr is not None else
                    f"当前有效区间不足或价格变化太一致，无法可靠计算相关系数；两者同时下跌 {co_down} 段。"
                ),
                "idea": "相关性高时，简单把钱拆成两份未必能分散风险；相关性低也不能保证危机时不会一起跌。",
                "next": "研究共同下跌区间的组合风险，以及 50/50、波动率控制和持有现金基线的风险差异。",
            },
            {
                "title": "图 4｜两种资产的关系会随时间改变吗？",
                "read": f"每点只计算截至该日期过去 {ROLLING_PAIRS} 个共同报价间隔的收益相关性，不引用之后的数据。",
                "finding": (
                    f"历史滚动相关系数在 {roll_min:+.2f} 到 {roll_max:+.2f} 之间变化；"
                    f"最近一个可计算值为 {summary['rolling_corr_latest']:+.2f}。"
                    if roll_min is not None else
                    f"共同报价间隔不足 {ROLLING_PAIRS} 段，暂时不能得出滚动相关性变化的结论。"
                ),
                "idea": "如果资产关系并不稳定，固定不变的配置比例可能不适合所有市场阶段；可比较动态风险配置。",
                "next": "只用过去窗口估计配置规则，并以按时间先后的样本外区间验证，避免事后挑最优权重。",
            },
            {
                "title": "图 5｜两种资产历史上最大跌幅谁更大？",
                "read": "曲线从当时已观察到的最高价计算回撤；曲线为负代表已经从此前高点下跌。",
                "finding": f"在共同报价日内，黄金最低回撤 {gd:.1f}%，比特币最低回撤 {bd:.1f}%。这不是策略账户回撤。",
                "idea": "尝试设定仓位限制、持有现金或波动率阈值，观察能否降低大跌时的组合风险。",
                "next": "把风险控制方案与买入持有基线比较；同时算最终收益、实际组合回撤和扣除的手续费。",
            },
            {
                "title": "日期检查｜黄金不开市时，比特币仍能交易",
                "read": "不同市场的开市日不相同；这里没有把黄金周末的价格复制、预测或填成零。",
                "finding": (
                    f"比特币有 {summary['bitcoin_observed_days']} 个有效报价日，黄金有 "
                    f"{summary['gold_observed_days']} 个，其中 {btc_only} 个比特币报价日"
                    "没有相同日期的黄金报价。"
                ),
                "idea": "交易执行器需要两套日历：黄金休市保持原有黄金仓位，比特币仍可独立决策。",
                "next": "设计周末、节假日交易用例，检查手续费、现金余额和禁止未来价格泄漏。",
            },
        ]
    return [
        {
            "title": "Chart 1 | Normalized price comparison",
            "read": "Both indexes start at 100 on the first observed common date; they are not portfolio values.",
            "finding": (f"Across {summary['common_quote_days']} common quotes, final indexes were "
                        f"gold {summary['gold_end_index']:.1f}, Bitcoin {summary['bitcoin_end_index']:.1f}."),
            "idea": "Compare cash-hold, gold buy-and-hold and Bitcoin buy-and-hold before fee-aware rebalancing.",
            "next": "Use a causal fee-aware backtest, not the known hindsight winner.",
        },
        {
            "title": "Chart 2 | Return changes on matched quote intervals",
            "read": "Both returns span exactly the same consecutive common-date interval, which may include market closures.",
            "finding": (f"{n} matched intervals; gold volatility "
                        f"{summary['gold_interval_volatility_pct']:.2f}%, Bitcoin "
                        f"{summary['bitcoin_interval_volatility_pct']:.2f}%."
                        if summary["gold_interval_volatility_pct"] is not None else
                        f"Only {n} interval(s): insufficient evidence for volatility comparison."),
            "idea": "Test risk limits and lower-turnover fee-aware strategies where risk differs.",
            "next": "Compare net return, max portfolio drawdown, turnover and transaction fees.",
        },
        {
            "title": "Chart 3 | Paired-return relationship",
            "read": "Each dot pairs gold and Bitcoin returns over the same common-date interval.",
            "finding": (f"Historical return correlation {corr:+.2f}; "
                        f"both negative in {co_down} intervals ({rate:.1f}%)."
                        if corr is not None else
                        f"Correlation unavailable; {co_down} simultaneous down intervals."),
            "idea": "Test whether diversification holds during simultaneous losses rather than assuming low average correlation is safe.",
            "next": "Compare cash, 50/50, and risk-limited portfolios in stress periods.",
        },
        {
            "title": "Chart 4 | Rolling correlation",
            "read": f"Trailing {ROLLING_PAIRS} common-quote return intervals, using past observations only.",
            "finding": (f"Rolling correlation ranged {roll_min:+.2f} to {roll_max:+.2f}."
                        if roll_min is not None else "Insufficient matched observations for rolling correlation."),
            "idea": "Test whether a time-varying portfolio rule withstands changing market relationships.",
            "next": "Train on earlier dates; validate later dates without look-ahead.",
        },
        {
            "title": "Chart 5 | Drawdowns on common observation dates",
            "read": "Each price index measured below its previously observed peak, not a portfolio strategy.",
            "finding": f"Gold drawdown {gd:.1f}%; Bitcoin drawdown {bd:.1f}%.",
            "idea": "Consider risk budgets and cash exposure to address severe joint losses.",
            "next": "Report actual strategy drawdown alongside fee-adjusted final wealth.",
        },
        {
            "title": "Calendar | What happens on gold-closed days?",
            "read": "No forward/back-fill or fabricated executable gold quote is created.",
            "finding": (f"Bitcoin has {summary['bitcoin_observed_days']} valid dates; "
                        f"gold {summary['gold_observed_days']}; {btc_only} BTC-only dates."),
            "idea": "Model separate gold and BTC trading calendars, with gold held through closures.",
            "next": "Test weekend/holiday trades, cash balances, and no-future-data constraints.",
        },
    ]


def _interpret(story: dict[str, str], zh: bool) -> None:
    for cn, en, key in (
        ("这张图怎么看", "How to read", "read"),
        ("这份数据发现了什么", "Measured finding", "finding"),
        ("对建模有什么启发", "Modeling inspiration", "idea"),
        ("下一步怎么验证", "Next experiment", "next"),
    ):
        st.write(f"**{cn if zh else en}：** {story[key]}")


def _display_market_charts(aligned: pd.DataFrame, summary: dict[str, Any], *, zh: bool) -> None:
    stories = joint_chart_explanations(summary, "zh" if zh else "en")
    paired = aligned[["gold_price", "bitcoin_price"]].pct_change().iloc[1:] * 100
    paired.columns = ["gold_return_pct", "bitcoin_return_pct"]
    normalized = aligned[["gold_index", "bitcoin_index"]]
    drawdown = normalized.div(normalized.cummax()).sub(1) * 100
    keep_every = max(1, len(aligned) // 500)

    st.markdown(f"#### {stories[0]['title']}")
    st.line_chart(normalized.iloc[::keep_every].rename(columns={
        "gold_index": "黄金 (起点=100)" if zh else "Gold (start=100)",
        "bitcoin_index": "比特币 (起点=100)" if zh else "Bitcoin (start=100)",
    }), width="stretch")
    _interpret(stories[0], zh)

    st.markdown(f"#### {stories[1]['title']}")
    st.line_chart(paired.iloc[::max(1, len(paired) // 500)].rename(columns={
        "gold_return_pct": "黄金区间收益 (%)" if zh else "Gold interval return (%)",
        "bitcoin_return_pct": "比特币区间收益 (%)" if zh else "BTC interval return (%)",
    }), width="stretch")
    _interpret(stories[1], zh)

    st.markdown(f"#### {stories[2]['title']}")
    st.scatter_chart(paired.rename(columns={
        "gold_return_pct": "黄金 (%)" if zh else "Gold return (%)",
        "bitcoin_return_pct": "比特币 (%)" if zh else "Bitcoin return (%)",
    }), x="黄金 (%)" if zh else "Gold return (%)",
        y="比特币 (%)" if zh else "Bitcoin return (%)", width="stretch")
    _interpret(stories[2], zh)

    st.markdown(f"#### {stories[3]['title']}")
    if summary["rolling_corr_latest"] is not None:
        rolling = paired["gold_return_pct"].rolling(
            ROLLING_PAIRS, min_periods=ROLLING_PAIRS
        ).corr(paired["bitcoin_return_pct"])
        st.line_chart(rolling.dropna(), width="stretch")
    _interpret(stories[3], zh)

    st.markdown(f"#### {stories[4]['title']}")
    st.line_chart(drawdown.iloc[::keep_every].rename(columns={
        "gold_index": "黄金回撤 (%)" if zh else "Gold drawdown (%)",
        "bitcoin_index": "比特币回撤 (%)" if zh else "BTC drawdown (%)",
    }), width="stretch")
    _interpret(stories[4], zh)
    st.markdown(f"#### {stories[5]['title']}")
    _interpret(stories[5], zh)


def render_joint_eda_panel(bundle: DatasetBundle) -> dict[str, Any] | None:
    """Prominent user-requested joint analysis, source safe, no paid API call."""
    zh = get_locale() == "zh"
    st.markdown(
        "### 黄金 × 比特币：放在一起究竟能发现什么？"
        if zh else "### Gold × Bitcoin: What do the two datasets reveal together?"
    )
    gold_refs = [r for r in bundle.datasets if "USD (PM)" in r.column_names]
    btc_refs = [r for r in bundle.datasets if "Value" in r.column_names]
    if len(gold_refs) != 1 or len(btc_refs) != 1 or gold_refs[0].dataset_id == btc_refs[0].dataset_id:
        st.info(
            "联合市场研究适用于分别包含 Date、USD (PM) 和 Date、Value 的黄金、比特币原始文件。"
            if zh else
            "This analysis needs distinct gold (Date, USD (PM)) and BTC (Date, Value) datasets."
        )
        return None
    gold_ref, btc_ref = gold_refs[0], btc_refs[0]
    current = {
        "bundle_fingerprint": bundle.fingerprint,
        "gold_sha256": gold_ref.sha256,
        "bitcoin_sha256": btc_ref.sha256,
    }
    authorized = st.session_state.get(JOINT_EDA_SESSION_KEY) == current
    st.caption(
        "先临时按真实共同报价日期配对，不补黄金休市日，不生成可交易价格。"
        "点击下面的按钮才开始计算；原始两份 CSV 不会被改变或永久合并。"
        if zh else
        "Explicit, read-only matching of actual common quote dates; never fills missing gold days "
        "or persists a merged dataset. Select Analyze to start."
    )
    if st.button(
        "开始两市场联合分析（生成 5 张图及建模建议）"
        if zh else "Analyze both markets (5 charts + modeling insights)",
        key="joint_market_start_analysis",
        type="primary",
    ):
        st.session_state[JOINT_EDA_SESSION_KEY] = current
        authorized = True
    if not authorized:
        st.info("点击上面的按钮继续联合分析。" if zh else "Start the joint analysis above.")
        return None

    gold = bundle.loaded_dataset(gold_ref.dataset_id).frame
    btc = bundle.loaded_dataset(btc_ref.dataset_id).frame
    try:
        aligned, summary = calculate_joint_market_insights(gold, btc)
    except (ValueError, KeyError) as exc:
        st.error(
            ("联合分析无法进行：请检查重复日期、价格列及共同报价日。"
             if zh else "Joint analysis cannot run: inspect dates and prices.")
            + f" {exc}"
        )
        return None
    summary.update(current)
    cols = st.columns(4)
    cols[0].metric("共同报价日" if zh else "Common quote days", summary["common_quote_days"])
    cols[1].metric("仅比特币有价的日期" if zh else "BTC-only quote days", summary["bitcoin_only_days"])
    correlation = summary["paired_return_correlation"]
    cols[2].metric("历史收益相关性" if zh else "Return correlation",
                   f"{correlation:+.2f}" if correlation is not None else "不足以计算" if zh else "N/A")
    cols[3].metric("同时下跌区间" if zh else "Both assets declined",
                   f"{summary['both_negative_intervals']} / {summary['paired_return_intervals']}")
    st.warning(
        "注意：以下指标按相邻共同报价日计算，可能跨周末，不是自然日收益、交易信号或"
        "已经完成的组合回测。黄金 PM 报价和比特币报价的时间也可能不同，"
        "交易前必须单独确定信息何时可获得。"
        if zh else
        "Matched quote intervals can span weekends. These are neither daily returns, "
        "trading signals nor a strategy backtest. Quote publication/execution timing differs."
    )
    _display_market_charts(aligned, summary, zh=zh)
    st.success(
        "联合发现已准备好：点击下面的「完成 EDA · 保存并继续研究方案」，"
        "只保存统计摘要、来源指纹和研究启发，不保存合并后的价格行。"
        if zh else
        "Joint findings are ready. Use Finish EDA to save aggregate findings and source hashes, "
        "not joined price rows."
    )
    return summary
