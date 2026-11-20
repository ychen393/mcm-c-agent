"""Plain-language research playbook for 2022 MCM C (problem-intake stage).

The playbook explains how to do each requested task, not merely what the
prompt says. Examples are proposed approaches, never empirical findings.
"""
from __future__ import annotations

from app.i18n import get_locale

def research_playbook(locale: str = "zh") -> list[dict[str, str]]:
    if locale == "en":
        return [
            {"name":"1 · Define the daily decision","why":"The judges need an executable decision rule, not a statement that we will maximize profits.","inputs":"Initial $1,000; two price series; 1% gold and 2% Bitcoin transaction fees.","do":"Represent each day by cash, gold units and BTC units. Define buy, sell and hold actions; subtract fees from each trade; refuse gold trades on closed days. Trade only after the decision price is known.","deliver":"Portfolio update equations, fee accounting and a precise trade-timing convention.","check":"Can we reproduce the balances after a single buy and sell without using tomorrow's price?"},
            {"name":"2 · Inspect the data before choosing a method","why":"A strategy for a fairly stable asset may fail for an asset with frequent sharp losses.","inputs":"Uploaded gold and Bitcoin CSVs, exactly as provided.","do":"Check missing/duplicate dates, chart each price, quantify quote-to-quote moves, largest price drawdown and trailing volatility. Align two markets only on explicitly chosen calendar rules.","deliver":"A short data-quality report and several charts, each with a finding and a modeling implication.","check":"Were any gaps or market-closure days secretly treated as executable prices?"},
            {"name":"3 · Compare 3–4 candidate strategies","why":"Without a baseline, a complicated model cannot show what it improves.","inputs":"Problem constraints, measured EDA and training-only history.","do":"Begin with cash hold, gold buy-and-hold and Bitcoin buy-and-hold. Then test a fee-aware trend rule and/or risk-aware allocation; define each signal with historical prices only.","deliver":"Candidate table: signal, action, cost handling, assumptions, advantages and limitations.","check":"Is this a real implemented method or only a research proposal? Do we know exactly when its orders execute?"},
            {"name":"4 · Test and challenge the decision rule","why":"The best result on the full five-year dataset might simply exploit hindsight.","inputs":"Implemented strategy and baseline simulation outputs.","do":"Use chronological train/validation/test windows; calculate terminal wealth, drawdown, fees and turnover. Vary both commission rates and test parameter changes on later unseen dates.","deliver":"Comparison chart/table, sensitivity results and counterexamples.","check":"Would the ranking still hold on unseen periods and after commissions?"},
            {"name":"5 · Write the evidence-based solution","why":"An impressive final dollar value is not enough without a reproducible explanation.","inputs":"Equations, EDA, model comparisons, validation and limitations.","do":"Explain the selected policy and reasons, include 2021-09-10 final wealth, show sensitivity and write the trader memo in no more than two pages.","deliver":"Report + trader memo with reproducible figures, assumptions and a careful definition of optimal.","check":"Can a reader recreate the experiments, and are any claims stronger than the evidence?"},
        ]
    return [
        {"name":"① 先把“每天怎么操作”写成规则","why":"题目真正要的是一套每天可以照着执行的买卖规则，而不是一句“提高收益”。","inputs":"起始现金 1,000 美元、黄金与比特币价格、黄金 1% / 比特币 2% 的手续费。","do":"把账户拆成现金、持有多少黄金、持有多少比特币。规定每个交易日如何判断买、卖、持有；每次扣手续费；黄金休市不能操作。明确当天的价格几点才知道，不能提前拿来交易。","deliver":"持仓更新公式、手续费计算方法和清晰的成交时点。","check":"给定昨天的持仓和今天已知的价格，能否独立算出今天交易后的余额？"},
        {"name":"② 先看真实数据，再谈哪种模型合适","why":"如果某资产突然跌很多，仅看价格总体上涨就可能选出风险很大的方案。","inputs":"上传的两份原始 CSV。","do":"查缺失日期、重复数据、价格走势、每次涨跌幅、最大跌幅和滚动波动。黄金与比特币交易日不同，需要先确定比较规则，不能乱填不存在的行情。","deliver":"每张图都应回答“发现了什么 → 对建模有什么影响”，并给出数据质量结论。","check":"是否错误地把黄金周末的空白当成零价格，或用未来价格填空？"},
        {"name":"③ 列出不同方案，解释为何选它们","why":"只有和简单方案比较，才能知道复杂模型到底带来了什么价值。","inputs":"题目约束 + 第二步的统计结果。","do":"先做现金不动、只持黄金、只持比特币三个基线；再提出考虑手续费的趋势策略、限制大幅回撤的配置策略。逐个写明信号、决策、调仓条件、难点及需要验证的假设。","deliver":"至少 3–4 种思路的具体对照表、初步首选方案及替代方案。","check":"推荐的是已经有代码能跑的策略，还是下一步需要开发的研究想法？"},
        {"name":"④ 做实验，专门寻找模型的弱点","why":"用同一段历史反复调参数，再说模型很厉害，会受到“事后诸葛亮”偏差影响。","inputs":"已经实现的方案、基线策略和验证区间。","do":"按时间先后划分开发期与检验期；比较最终资产、最大回撤、总手续费、交易次数。分别改变黄金和比特币手续费，看看排名是否反转。","deliver":"策略对照图、参数与手续费敏感性图表、失败场景和局限性。","check":"模型在没参与调参的日期上还有效吗？扣费后仍胜过简单买入持有吗？"},
        {"name":"⑤ 写成别人能够复现的完整答卷","why":"只报一个期末金额，无法说明交易逻辑是否正确，也无法说服评委。","inputs":"模型公式、完整回测与敏感性结果、图表、参考资料和明确的限制。","do":"说明为何挑选该策略、2016–2021 年具体如何操作、2021-09-10 的最终资产是多少，以及手续费改变后有哪些差异；最后整理两页以内的交易员备忘录。","deliver":"附有图表、公式、验证、局限性和交易员备忘录的论文草稿。","check":"所有结论都能指向数据、计算步骤或证据吗？是否误称“全局最优”？"},
    ]

def render_research_playbook() -> None:
    import streamlit as st
    zh = get_locale() == "zh"
    st.markdown("### 具体怎么做：五步研究施工图" if zh else "### The actual research plan, step by step")
    st.caption(
        "这些是针对赛题的可实施研究步骤，不代表实验已经完成。第二阶段会用真实数据修正模型选择。"
        if zh else
        "This is a proposed research recipe, not finished experiments. Data analysis changes model choice."
    )
    for item in research_playbook("zh" if zh else "en"):
        with st.expander(item["name"], expanded=True):
            st.markdown(("**为什么要做** " if zh else "**Why** ") + item["why"])
            st.markdown(("**需要什么** " if zh else "**Inputs** ") + item["inputs"])
            st.markdown(("**具体操作** " if zh else "**What to do** ") + item["do"])
            st.markdown(("**产出** " if zh else "**Deliverable** ") + item["deliver"])
            st.markdown(("**验收问题** " if zh else "**Check** ") + item["check"])
