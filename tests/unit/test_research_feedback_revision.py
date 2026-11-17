"""Explicit human-feedback revision must change proposals, not just labels."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.research_revision import revise_with_feedback
from core.config import get_settings
from tools.problem_spec_2022_c import load_2022_c_fixture


class FakeTwoModelCalls:
    def __init__(self, candidate_id: str, *, malformed: bool = False):
        self.calls = []
        self.candidate_id = candidate_id
        self.malformed = malformed

    def invoke(self, messages):
        self.calls.append(messages)
        if self.malformed:
            return SimpleNamespace(content="{broken", provider="mock", model="revision-mock")
        if len(self.calls) == 1:
            payload = {
                "candidate_id": self.candidate_id,
                "revised_summary": (
                    "Use only already-observed historical quotes to compute a "
                    "lagged trend signal; avoid buying gold on closed days, "
                    "explicitly debit 1% and 2% transaction fees; "
                    "compare the revised policy against cash and buy-hold; "
                    "evaluate chronological holdout dates and maximum drawdown."
                ),
                "changes_made": (
                    "Added commission-aware no-trade thresholds, a gold market "
                    "closure constraint and chronological validation to address "
                    "the human reviewer request."
                ),
                "next_tests": ["Compare turnover and fees", "Chronological holdout"],
                "remaining_risks": ["Parameters may be overfit"],
            }
            content = json.dumps(payload)
        else:
            content = "Independent reviewer: check availability of prices at decision time, explain model feasibility and compare against buy-hold; H1 remains pending."
        return SimpleNamespace(content=content, provider="mock", model="revision-mock")


def _baseline():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    prior = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    return spec, prior


def test_user_feedback_produces_distinct_proposal_and_two_independent_calls():
    spec, original = _baseline()
    mock = FakeTwoModelCalls(original.recommended_candidate_id)
    feedback = "Please account for closed gold markets, fee drag and explicit chronological holdout."
    revised, history = revise_with_feedback(
        proposal=original,
        feedback=feedback,
        problem_specification=spec.model_dump(mode="json"),
        eda_report={"interpreted_findings":{"datasets":[{
            "name":"LBMA-GOLD.csv","rows":1200,"valid_prices":1200,
            "volatility_pct":1.2,"max_drawdown_pct":-15.0,
            "missing_by_column":{"USD (PM)":0}
        }]}},
        settings=get_settings(),
        llm=mock,
        language="en",
    )
    assert len(mock.calls) == 2
    assert "REVISER" in mock.calls[0][0]["content"]
    assert "INDEPENDENT research critic" in mock.calls[1][0]["content"]
    assert revised.proposal_id != original.proposal_id
    assert revised.recommended_candidate_id in [c.candidate_id for c in revised.candidates]
    assert history["feedback"] == feedback
    assert history["before"] != history["after"]
    assert "transaction fees" in history["after"]
    assert "H1 remains pending" in history["critic_feedback"]
    assert "approval_status" not in history


def test_malformed_llm_revision_leaves_original_input_unchanged():
    spec, original = _baseline()
    before = original.model_dump(mode="json")
    mock = FakeTwoModelCalls(original.recommended_candidate_id, malformed=True)
    with pytest.raises(ValueError):
        revise_with_feedback(
            proposal=original,
            feedback="We must revise fee handling and market calendars before approval.",
            problem_specification=spec.model_dump(mode="json"),
            eda_report=None,
            settings=get_settings(),
            llm=mock,
        )
    assert len(mock.calls) == 1
    assert original.model_dump(mode="json") == before


def test_feedback_is_required_and_not_replaced_by_generic_rerun():
    spec, original = _baseline()
    mock = FakeTwoModelCalls(original.recommended_candidate_id)
    with pytest.raises(ValueError, match="12"):
        revise_with_feedback(
            proposal=original, feedback="fix it",
            problem_specification=spec.model_dump(mode="json"),
            eda_report=None, settings=get_settings(), llm=mock,
        )
    assert mock.calls == []
