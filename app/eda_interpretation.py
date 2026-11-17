"""Auditable, non-LLM EDA specialist with human explanations.

Only observations from uploaded in-memory frames are used; never fill future
prices or persist raw observations. Results are descriptive, not causal claims.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from app.i18n import get_locale
from app.eda_story import chart_stories, render_chart_interpretation
from tools.dataset_bundle import DatasetBundle


def _pick_price_column(frame: pd.DataFrame) -> str | None:
    for preferred in ("USD (PM)", "Value", "Close", "price", "Price"):
        if preferred in frame:
            return preferred
    options = [
        col for col in frame.columns if col != "Date"
        and pd.to_numeric(frame[col], errors="coerce").notna().sum() > 2
    ]
    return options[0] if options else None


def analyze_market_frame(frame: pd.DataFrame, *, name: str = "") -> dict[str, Any]:
    """Compact price profiling; no hidden interpolation or prospective signals."""
    if frame.empty:
        raise ValueError("Cannot analyze an empty dataset")
    date_col = next(
        (col for col in frame.columns if str(col).strip().lower() in {"date", "datetime", "timestamp"}),
        None,
    )
    price_col = _pick_price_column(frame)
    dates = (
        pd.to_datetime(frame[date_col], errors="coerce")
        if date_col is not None else pd.Series(dtype="datetime64[ns]")
    )
    missing_by_column = {
        str(col): int(frame[col].isna().sum()) for col in frame.columns
    }
    info: dict[str, Any] = {
        "name": name,
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "date_column": date_col,
        "price_column": price_col,
        "missing_by_column": missing_by_column,
        "duplicate_dates": int(dates.dropna().duplicated().sum()),
        "invalid_dates": int(dates.isna().sum()) if date_col is not None else None,
        "date_start": None,
        "date_end": None,
        "valid_prices": 0,
        "start_price": None,
        "end_price": None,
        "change_pct": None,
        "volatility_pct": None,
        "max_drawdown_pct": None,
        "largest_daily_move_pct": None,
    }
    if date_col is None or price_col is None:
        return info
    prices = pd.to_numeric(frame[price_col], errors="coerce")
    valid = pd.DataFrame({"date": dates, "price": prices}).dropna()
    valid = valid[valid["price"] > 0].sort_values("date")
    if valid.empty:
        return info
    info["valid_prices"] = int(len(valid))
    info["date_start"] = valid["date"].iloc[0].strftime("%Y-%m-%d")
    info["date_end"] = valid["date"].iloc[-1].strftime("%Y-%m-%d")
    info["start_price"] = float(valid["price"].iloc[0])
    info["end_price"] = float(valid["price"].iloc[-1])
    if len(valid) > 1:
        returns = valid["price"].pct_change().dropna()
        info["change_pct"] = float((valid["price"].iloc[-1] / valid["price"].iloc[0] - 1) * 100)
        info["volatility_pct"] = float(returns.std(ddof=1) * 100) if len(returns) >= 2 else None
        info["largest_daily_move_pct"] = float(returns.abs().max() * 100)
        drawdown = valid["price"] / valid["price"].cummax() - 1
        info["max_drawdown_pct"] = float(drawdown.min() * 100)
    return info


def bundle_insights(bundle: DatasetBundle) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for ref in bundle.datasets:
        info = analyze_market_frame(
            bundle.loaded_dataset(ref.dataset_id).frame,
            name=ref.file_name,
        )
        info["dataset_id"] = ref.dataset_id
        info["sha256"] = ref.sha256
        items.append(info)
    return {
        "source": "uploaded_dataset_profiles",
        "bundle_fingerprint": bundle.fingerprint,
        "method": "deterministic_descriptive_statistics",
        "datasets": items,
        "jointly_modeled": False,
    }


def _plot_market(frame: pd.DataFrame, summary: dict[str, Any], zh: bool) -> None:
    date_col, price_col = summary["date_column"], summary["price_column"]
    if not date_col or not price_col:
        st.warning("缺少日期或价格列，无法计算价格图。" if zh else
                   "No usable date/price column; cannot produce price charts.")
        return
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    prices = pd.to_numeric(frame[price_col], errors="coerce")
    data = pd.DataFrame({"date": dates, "price": prices}).dropna()
    data = data[data.price > 0].sort_values("date").drop_duplicates("date", keep="last")
    if len(data) < 2:
        st.warning("有效价格不足两行。" if zh else "Fewer than two valid quotes.")
        return
    data = data.set_index("date")
    returns = data["price"].pct_change().dropna() * 100
    drawdown = (data["price"] / data["price"].cummax() - 1) * 100
    pct = summary.get("change_pct")
    vola = summary.get("volatility_pct")
    stories = chart_stories(frame, summary, language="zh" if zh else "en")
    if zh:
        st.markdown("**图 1 · 历史价格趋势**")
        st.caption(f"展示原始报价的趋势与波动；首尾价格变化 {pct:+.1f}% "
                   "不等于可以事先获得的投资收益，也不能证明未来走势。"
                   if pct is not None else "展示观察到的历史价格，不补齐缺失交易日。")
    else:
        st.markdown("**Chart 1 · Historical prices**")
        st.caption(f"Observed change {pct:+.1f}% is not an attainable future forecast."
                   if pct is not None else "Observed quotes only.")
    sample = data.iloc[::max(1, len(data)//500)]
    st.line_chart(sample["price"], width="stretch")
    if stories.get("price"):
        render_chart_interpretation(stories["price"], language="zh" if zh else "en")

    st.markdown("**图 2 · 相邻报价日收益率分布**" if zh else
                "**Chart 2 · Between-observation return distribution**")
    if zh:
        st.caption("用于观察涨跌幅分布是否极端、是否存在较长尾部；"
                   "黄金的相邻报价日不一定间隔 24 小时，不能直接和比特币自然日收益等同。")
    else:
        st.caption("Shows extreme moves; a gold quote-to-quote interval may span market closure days.")
    counts, edges = np.histogram(returns.to_numpy(), bins=min(30, max(5, int(np.sqrt(len(returns))))))
    hist = pd.DataFrame(
        {"频数" if zh else "Count": counts},
        index=[f"{edges[i]:+.1f}% to {edges[i+1]:+.1f}%" for i in range(len(counts))]
    )
    st.bar_chart(hist, width="stretch")
    if stories.get("returns"):
        render_chart_interpretation(stories["returns"], language="zh" if zh else "en")

    st.markdown("**图 3 · 历史峰值回撤**" if zh else "**Chart 3 · Price drawdown from past peaks**")
    st.caption(
        "显示价格相对截至当日历史峰值的跌幅，用于制定风控要求；"
        "这是资产价格回撤，尚不是策略组合回撤。"
        if zh else
        "Price drawdown from peaks available up to each date; not yet a portfolio backtest."
    )
    st.line_chart(drawdown.iloc[::max(1, len(drawdown)//500)], width="stretch")
    if stories.get("drawdown"):
        render_chart_interpretation(stories["drawdown"], language="zh" if zh else "en")

    st.markdown("**图 4 · 滚动波动率**" if zh else "**Chart 4 · Rolling realized volatility**")
    if len(returns) >= 20:
        vol = returns.rolling(20, min_periods=20).std().dropna()
        st.line_chart(vol.iloc[::max(1, len(vol)//500)], width="stretch")
        st.caption("过去 20 个有效报价间隔的收益率标准差；仅用历史值、不年化，"
                   "作为风险动态变化的线索。" if zh else
                   "Trailing 20-observation standard deviation; not annualized and not a forecast.")
    else:
        st.caption("有效收益率少于 20 个，暂不能计算可靠的滚动波动率。"
                   if zh else "Fewer than 20 returns; rolling volatility not shown.")
    if stories.get("rolling"):
        render_chart_interpretation(stories["rolling"], language="zh" if zh else "en")


def render_explainable_eda(bundle: DatasetBundle) -> dict[str, Any]:
    """Render four charts per suitable dataset plus quantified interpretation."""
    zh = get_locale() == "zh"
    insight = bundle_insights(bundle)
    st.markdown("### 数据分析师：数据告诉了我们什么？" if zh
                else "### EDA specialist: What do the data actually show?")
    st.caption(
        "统计与图表均由已上传的数据离线计算；这些是描述性证据，不是模型优化结果。"
        if zh else
        "All statistics and charts come from uploaded in-memory rows; descriptive evidence only."
    )
    tabs = st.tabs([r.file_name for r in bundle.datasets])
    for tab, ref, info in zip(tabs, bundle.datasets, insight["datasets"], strict=True):
        with tab:
            frame = bundle.loaded_dataset(ref.dataset_id).frame
            cols = st.columns(4)
            cols[0].metric("记录数" if zh else "Rows", info["rows"])
            cols[1].metric("有效价格" if zh else "Valid quotes", info["valid_prices"])
            cols[2].metric("缺失单元格" if zh else "Missing cells", sum(info["missing_by_column"].values()))
            cols[3].metric("日期重复" if zh else "Duplicate dates", info["duplicate_dates"])
            if info["date_start"]:
                st.caption(f"{info['date_start']} → {info['date_end']} · {info['price_column']}")
            if info["volatility_pct"] is not None:
                st.write(
                    (f"**关键发现：** 有效相邻报价收益率的标准差约 "
                     f"{info['volatility_pct']:.2f}%；历史最大价格回撤 "
                     f"{info['max_drawdown_pct']:.1f}%。"
                     "手续费和风险管理应进入下一阶段的模型比较。")
                    if zh else
                    (f"**Finding:** Quote-to-quote return standard deviation "
                     f"{info['volatility_pct']:.2f}%; maximum price drawdown "
                     f"{info['max_drawdown_pct']:.1f}%. "
                     "Transaction costs and risk controls should inform candidate selection.")
                )
            if info["duplicate_dates"] or info["invalid_dates"] or sum(info["missing_by_column"].values()):
                st.warning(
                    ("存在重复、无效日期或缺失值；进行策略回测前必须逐项核对。"
                     if zh else "Duplicate/invalid dates or missing values require review before backtesting.")
                )
            _plot_market(frame, info, zh)
            with st.expander("数据质量细节 / Data quality detail", expanded=False):
                st.dataframe(
                    pd.DataFrame(
                        [{"列" if zh else "Column": k,
                          "缺失数" if zh else "Missing": v}
                         for k, v in info["missing_by_column"].items()]
                    ),
                    hide_index=True, width="stretch",
                )
    st.markdown("### 这些数据如何决定下一步建模？" if zh else "### How these measurements shape the next experiment")
    if len(insight["datasets"]) >= 2:
        st.write(
            "你不是在两条价格曲线里“挑涨得最多的资产”，而是在比较两类不一样的风险。" if zh
            else "The goal is not to pick the line that rose most; the two markets expose different risks."
        )
        for row in insight["datasets"]:
            dd = row.get("max_drawdown_pct")
            if dd is not None:
                st.write(f"**{row['name']}：** "+ (
                    f"观察到资产价格最大回撤 {dd:.1f}%；先把该资产的买入持有作为基线，"
                    "再检查加入风控/手续费后是否更好。" if zh else
                    f"Observed price drawdown {dd:.1f}%. Compare against buy-and-hold before adding risk controls."
                ))
        st.warning(
            "黄金开市间隔与比特币自然日不同。若要比较收益率或相关性，必须明确共同观察日期，"
            "不能把缺失日期随意补成价格；图表结论不是最优策略的证明。" if zh else
            "Gold and Bitcoin have different quote calendars. Align observed dates explicitly; "
            "never fill unobserved tradable prices, and do not claim an optimal strategy from EDA."
        )
    st.info(
        "如何用于模型：通过 EDA 识别高波动、潜在回撤和休市缺口；下一阶段应该"
        "比较低换手率基线、趋势策略、风险控制策略，并用手续费敏感性与样本外检验区分。"
        if zh else
        "How EDA affects modeling: observed volatility, drawdowns and closures suggest "
        "benchmarking passive strategies, cost-aware momentum and risk controls."
    )
    return insight
