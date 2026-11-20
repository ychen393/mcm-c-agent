"""Readability checks: chart explanations must cite actual uploaded observations."""
import pandas as pd

from app.eda_interpretation import analyze_market_frame
from app.eda_story import chart_stories
from app.research_playbook import research_playbook
from app.research_decision_story import plan_readable


def test_each_price_chart_contains_observation_and_actionable_model_idea():
    data = pd.DataFrame({
        "Date": pd.date_range("2021-01-01",periods=40,freq="D").astype(str),
        "Value": [100+i * (-1 if i%3==0 else 2) for i in range(40)],
    })
    summary=analyze_market_frame(data,name="BCHAIN-MKPRU.csv")
    zh=chart_stories(data,summary,language="zh")
    en=chart_stories(data,summary,language="en")
    assert set(zh)==set(en)=={"price","returns","drawdown","rolling"}
    for key in zh:
        assert "建模" in zh[key]["inspiration"] or "策略" in zh[key]["inspiration"] or "仓位" in zh[key]["inspiration"] or "模型" in zh[key]["inspiration"] or "手续费" in zh[key]["inspiration"]
        assert zh[key]["finding"] != en[key]["finding"]
        assert zh[key]["test"]
    assert f"{summary['change_pct']:+.1f}%" in zh["price"]["finding"]
    assert "95%" in zh["returns"]["finding"]
    assert "最大" in zh["drawdown"]["finding"]


def test_problem_playbook_explains_actions_inputs_and_checks_in_two_languages():
    zh=research_playbook("zh")
    en=research_playbook("en")
    assert len(zh)==len(en)==5
    for item in zh:
        assert all(item[x] for x in ("why","inputs","do","deliver","check"))
    assert "1,000" in zh[0]["inputs"]
    assert "手续费" in zh[0]["do"]
    assert "chronological" in en[3]["do"].lower() or "train/validation" in en[3]["do"].lower()


def test_strategy_approach_has_concrete_rule_and_test():
    plan=plan_readable({"method_family":"trend_following"},language="zh")
    assert "过去" in plan["how"]
    assert "手续费" in plan["risk"]
    assert "回看" in plan["test"]
