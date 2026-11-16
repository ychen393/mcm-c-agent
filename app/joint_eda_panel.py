"""Opt-in, ephemeral joint EDA for the two 2022 MCM C price series.

Never persists merged rows, never imputes missing gold quotes, and cannot
satisfy an H1/H2/H3 approval by itself.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from tools.dataset_bundle import DatasetBundle


def calculate_joint_market_view(gold: pd.DataFrame, btc: pd.DataFrame) -> pd.DataFrame:
    """Align observed trading dates; return normalized prices for charting.

    A bitcoin Sunday with no gold quote is not filled; the result includes only
    dates with observed gold and bitcoin prices, with all dates in increasing order.
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


def render_joint_eda_panel(bundle: DatasetBundle) -> None:
    """Only run after explicit two-dataset preview confirmation for this bundle."""
    st.markdown("#### 黄金 × 比特币联合观察 / Joint price exploration")
    confirmation = st.session_state.get("integration_preview_confirmation")
    if not isinstance(confirmation, dict) or not confirmation.get("confirmed"):
        st.info("先预览并确认两份数据的日期关系，再选择联合分析；不会自动合并。")
        return
    if confirmation.get("join_type") != "inner":
        st.warning("该比较仅支持日期 Inner Join，不进行缺失值填补。")
        return
    normal_preview = confirmation.get("status") == "preview"
    calendar_override = (
        confirmation.get("status") == "blocked"
        and confirmation.get("reason") == "frequency_mismatch"
    )
    if not normal_preview and not calendar_override:
        st.warning("该日期关系未通过安全检查；不可执行联合分析。")
        return
    if calendar_override:
        st.warning(
            "黄金只在开市日报价，比特币每天报价；两市场频率不同。"
            "此专项比较只保留双方实际有报价的日期，不进行周末价格填充。"
        )
        if not st.checkbox(
            "我同意仅比较共同报价日期 / Confirm observed-date-only alignment",
            key="joint_eda_calendar_ack",
        ):
            return
    ids = {ref.dataset_id: ref for ref in bundle.datasets}
    left_id = confirmation.get("left_dataset_id")
    right_id = confirmation.get("right_dataset_id")
    if left_id not in ids or right_id not in ids:
        st.warning("数据文件已变化。请重新预览和确认新的数据集。")
        return
    if confirmation.get("left_key") != "Date" or confirmation.get("right_key") != "Date":
        st.warning("请将两份数据都选择 Date 键，进行日期关系预览。")
        return

    gold_ref = next((r for r in bundle.datasets if "USD (PM)" in r.column_names), None)
    btc_ref = next((r for r in bundle.datasets if "Value" in r.column_names), None)
    if not gold_ref or not btc_ref or {gold_ref.dataset_id, btc_ref.dataset_id} != {left_id, right_id}:
        st.warning("该专项联合图表需要黄金价格列 USD (PM) 与比特币价格列 Value。")
        return

    st.caption("只做内存中的已确认日期配对。无跨日期填充、无未来信息补全、无自动保存。")
    if st.button("生成联合价格对比图 / Plot joint analysis", key="joint_eda_confirm_run"):
        try:
            joined = calculate_joint_market_view(
                bundle.loaded_dataset(gold_ref.dataset_id).frame,
                bundle.loaded_dataset(btc_ref.dataset_id).frame,
            )
        except (ValueError, KeyError) as exc:
            st.error(f"联合分析无法运行：{exc}")
        else:
            st.session_state["joint_eda_chart"] = {
                "bundle_fingerprint": bundle.fingerprint,
                "rows": len(joined),
                "gold_index": joined["gold_index"].to_list(),
                "bitcoin_index": joined["bitcoin_index"].to_list(),
                "dates": [v.strftime("%Y-%m-%d") for v in joined.index],
            }
    result = st.session_state.get("joint_eda_chart")
    if not isinstance(result, dict) or result.get("bundle_fingerprint") != bundle.fingerprint:
        return
    st.metric("两市场共同报价日期 / Overlapping quote dates", int(result["rows"]))
    chart = pd.DataFrame(
        {"Gold (start=100)": result["gold_index"],
         "Bitcoin (start=100)": result["bitcoin_index"]},
        index=pd.to_datetime(result["dates"]),
    )
    st.line_chart(chart, width="stretch")
    st.caption("仅展示两个市场均有报价的日期，曲线以首日=100标准化。不是交易信号，也不是回测。")
