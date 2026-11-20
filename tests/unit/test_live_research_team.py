"""Explicit two-call model collaboration uses no new approvals and no raw prices."""
from __future__ import annotations

from types import SimpleNamespace

from agents.live_research_team import run_live_research_team
from core.config import get_settings


class FakeResearchLLM:
    def __init__(self):
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return SimpleNamespace(
            content="Candidate comparison with cost-aware tests" if len(self.messages) == 1
            else "Reviewer: inspect lookahead, commissions and holdout",
            provider="mock",
            model="offline-test",
        )


def test_live_team_has_separate_strategist_and_critic_calls_without_approval():
    mock = FakeResearchLLM()
    specification = {
        "title": "Gold and Bitcoin",
        "research_questions": [{"statement": "Choose a causal strategy"}],
        "constraints": [{"statement": "No future prices"}],
    }
    proposal = {
        "proposal_id": "prop_test",
        "candidates": [{
            "candidate_id": "cand_test", "method_family": "trend_following",
            "summary": "Lagged moving-average rule, not yet validated",
        }],
    }
    eda = {"interpreted_findings": {"datasets": [{
        "name": "LBMA-GOLD.csv", "rows": 50, "valid_prices": 49,
        "volatility_pct": 1.2, "max_drawdown_pct": -8.0,
        "missing_by_column": {"USD (PM)": 1},
    }]}}
    result = run_live_research_team(
        specification=specification,
        proposal=proposal,
        eda_report=eda,
        settings=get_settings(),
        llm=mock,
        language="zh",
    )
    assert len(mock.messages) == 2
    assert "mathematical modeling research strategist" in mock.messages[0][0]["content"]
    assert "INDEPENDENT skeptical reviewer" in mock.messages[1][0]["content"]
    assert "Candidate comparison" in mock.messages[1][1]["content"]
    assert result["mode"] == "real_llm_two_call_advisory"
    assert "approval_status" not in result
    assert "decision_report" not in result
    assert "No future prices" in mock.messages[0][1]["content"]
