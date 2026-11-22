"""Mock-only typed strategist/critic → H1 version binding regression."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agents.research_evidence import build_research_evidence_packet
from agents.research_decision import with_research_decision
from agents.structured_research_team import run_structured_research_team
from core.config import get_settings
from core.project_store import LocalProjectStore
from modeling.preflight import research_execution_preflight
from schemas.research import CandidateMethod, ResearchProposal, DebateCritique
from tools.research_persistence import (
    build_h1_decision, persist_h1_decision_into_state,
    persist_research_proposal_into_state, proposal_sha256,
)


def _evidence():
    return {"interpreted_findings": {
        "bundle_fingerprint": "b2",
        "datasets": [
            {"name": "LBMA-GOLD.csv", "sha256": "a" * 64, "valid_prices": 40},
            {"name": "BCHAIN-MKPRU.csv", "sha256": "b" * 64, "valid_prices": 49},
        ],
        "joint_market": {"bundle_fingerprint": "b2",
                         "gold_sha256": "a" * 64, "bitcoin_sha256": "b" * 64,
                         "paired_return_intervals": 38,
                         "common_quote_days": 39, "bitcoin_only_days": 10,
                         "both_negative_intervals": 7,
                         "paired_return_correlation": 0.28},
    }}


def _proposal():
    original = ResearchProposal(
        proposal_id="prop_before_structured", problem_id="mcm_2022_c",
        recommended_candidate_id="cand_cost",
        candidates=[CandidateMethod(
            candidate_id="cand_cost", title="Fee aware strategy",
            method_family="cost_aware_trading",
            summary="A concrete fee-aware trading research hypothesis",
        ), CandidateMethod(
            candidate_id="cand_risk", title="Risk control strategy",
            method_family="risk_management",
            summary="A candidate risk-limited portfolio method",
        )],
        problem_specification_present=True, eda_context_present=True,
    )
    return with_research_decision(original, _evidence())


class FakeTeam:
    def __init__(self, *, malformed=False, invented=False):
        self.calls = []
        self.malformed = malformed
        self.invented = invented

    def invoke(self, messages):
        self.calls.append(messages)
        if len(self.calls) == 1:
            if self.malformed:
                return SimpleNamespace(content="{bad", provider="mock", model="offline")
            context = json.loads(messages[1]["content"])
            target = context["shortlist"][0]
            plan = dict(target["execution_plan"])
            plan["signal_definition"] = (
                "A past-only fee-aware threshold with a longer rolling window, "
                "explicit trading-day eligibility and no lookahead."
            )
            if self.invented:
                plan["implementation_status"] = "implemented"
                plan["executable_strategy_id"] = "unverified_new_model"
            response = {
                "candidate_id": target["candidate_id"],
                "revised_summary": (
                    "Use lagged price observations, assess a no-trade band "
                    "and calculate commissions on each executed trade; "
                    "compare against gold and Bitcoin buy-and-hold with a holdout."
                ),
                "revised_execution_plan": plan,
                "changes_made": "Added a lagged fee-aware signal and separate chronological validation.",
                "evidence_refs": plan["evidence_refs"],
            }
            return SimpleNamespace(content=json.dumps(response), provider="mock", model="offline")
        candidate = json.loads(messages[1]["content"])["revised_candidate"]
        reply = {
            "notes": [{
                "kind": "validation", "priority": "important",
                "candidate_id": candidate["candidate_id"],
                "target_field": "validation_design",
                "problem": "Parameters still need out-of-sample evaluation, not only in-sample charts.",
                "suggested_fix": "Compare with chronological holdout and fee-adjusted baselines.",
            }, {
                "kind": "future_work", "priority": "future_work",
                "candidate_id": candidate["candidate_id"],
                "target_field": "objective",
                "problem": "A global optimum is not proven by a historical backtest.",
                "suggested_fix": "Discuss optimality limitations in the final report rather than block H1.",
            }],
            "verdict": "ready_for_human_review",
        }
        return SimpleNamespace(content=json.dumps(reply), provider="mock", model="offline")


def test_two_structured_calls_revise_official_proposal_and_independent_critic():
    original = _proposal()
    provider = FakeTeam()
    revised, critique, audit = run_structured_research_team(
        specification={"title": "2022 MCM C", "constraints": [
            {"statement": "Gold fee 1%, Bitcoin fee 2%"},
        ]},
        proposal=original,
        eda_report=_evidence(),
        settings=get_settings(),
        llm=provider,
        language="en",
    )
    assert len(provider.calls) == 2
    assert revised.proposal_id != original.proposal_id
    assert revised.research_decision.primary_candidate_id == original.research_decision.primary_candidate_id
    assert critique.proposal_id == revised.proposal_id
    assert critique.blocking_count == 0
    assert {note.review_priority for note in critique.findings} == {"important", "future_work"}
    assert audit["evidence_packet_sha256"] == build_research_evidence_packet(_evidence())["packet_sha256"]
    assert next(x for x in revised.candidates if x.candidate_id == "cand_cost").execution_plan.signal_definition != (
        next(x for x in original.candidates if x.candidate_id == "cand_cost").execution_plan.signal_definition
    )
    assert revised.candidates[0].execution_plan.implementation_status == "needs_implementation"


@pytest.mark.parametrize("options, calls", [
    ({"malformed": True}, 1), ({"invented": True}, 1),
])
def test_bad_structured_response_never_edits_original_or_claims_success(options, calls):
    original = _proposal()
    before = original.model_dump(mode="json")
    provider = FakeTeam(**options)
    with pytest.raises(ValueError):
        run_structured_research_team(
            specification={"title": "2022 MCM C"}, proposal=original,
            eda_report=_evidence(), settings=get_settings(), llm=provider,
        )
    assert len(provider.calls) == calls
    assert original.model_dump(mode="json") == before


def test_h1_rejects_old_proposal_hash_and_modeling_is_blocked_even_if_research_approved(tmp_path):
    proposal = _proposal()
    critique = DebateCritique(
        critique_id="crit_sprint_a", proposal_id=proposal.proposal_id,
        findings=[], strategy="deterministic_rules",
    )
    store = LocalProjectStore(tmp_path / "projects")
    state = {
        "project_id": "sprint-a-study", "project_name": "Sprint A",
        "project_status": "initialized", "lifecycle": "data_analysis_done",
        "analysis_status": "data_analysis_done",
        "uploaded_files": [], "citations": [], "model_artifacts": [],
        "experiment_logs": [], "workspace_phases": {}, "approval_status": {},
        "errors": [], "data_resume": "reupload_required",
    }
    _p, run, first = store.save_project_state(
        project_id=state["project_id"], project_name=state["project_name"],
        state=state, input_signature="sig", note="initialize",
    )
    saved = persist_research_proposal_into_state(
        store, project_id=state["project_id"], project_name=state["project_name"],
        state={**first, "run_id": run.run_id}, input_signature="sig",
        proposal=proposal, critique=critique,
    )
    approved = build_h1_decision(
        status="approved", proposal=proposal,
        selected_candidate_id=proposal.recommended_candidate_id,
        critique_id=critique.critique_id,
    )
    stale = approved.model_copy(update={"proposal_sha256": "0" * 64})
    with pytest.raises(ValueError, match="stale"):
        persist_h1_decision_into_state(
            store, project_id=state["project_id"], project_name=state["project_name"],
            state=saved, input_signature="sig", decision=stale,
        )
    passed = persist_h1_decision_into_state(
        store, project_id=state["project_id"], project_name=state["project_name"],
        state=saved, input_signature="sig", decision=approved,
    )
    assert passed["approval_status"]["h1"] == "approved"
    readiness = research_execution_preflight(
        passed, selected_candidate_id=proposal.recommended_candidate_id,
    )
    assert not readiness["allowed"]
    assert "Sprint B" in readiness["reason"]
    assert proposal_sha256(proposal) == approved.proposal_sha256


def test_h1_cannot_approve_unresolved_blocking_critic(tmp_path):
    proposal = _proposal()
    critique = DebateCritique.model_validate({
        "critique_id": "crit_block",
        "proposal_id": proposal.proposal_id,
        "findings": [{
            "finding_id": "finding_missing_time",
            "kind": "contradiction", "severity": "blocking",
            "candidate_id": proposal.recommended_candidate_id,
            "statement": "Same-day information is treated as available before trading.",
            "suggested_action": "Use lagged signals before eligible execution.",
        }],
    })
    store = LocalProjectStore(tmp_path / "projects")
    state = {
        "project_id": "block-study", "project_name": "Block",
        "project_status": "initialized", "lifecycle": "data_analysis_done",
        "analysis_status": "data_analysis_done", "uploaded_files": [],
        "citations": [], "model_artifacts": [], "experiment_logs": [],
        "workspace_phases": {}, "approval_status": {},
        "errors": [], "data_resume": "reupload_required",
    }
    _p, run, first = store.save_project_state(
        project_id=state["project_id"], project_name=state["project_name"],
        state=state, input_signature="sig", note="init")
    saved = persist_research_proposal_into_state(
        store, project_id=state["project_id"], project_name=state["project_name"],
        state={**first, "run_id": run.run_id}, input_signature="sig",
        proposal=proposal, critique=critique,
    )
    decision = build_h1_decision(
        status="approved", proposal=proposal,
        selected_candidate_id=proposal.recommended_candidate_id,
        critique_id=critique.critique_id,
    )
    with pytest.raises(ValueError, match="blocking"):
        persist_h1_decision_into_state(
            store, project_id=state["project_id"], project_name=state["project_name"],
            state=saved, input_signature="sig", decision=decision,
        )



class FakeHumanReviser:
    """Two model-shaped messages per round; never external API traffic."""
    def __init__(self, *, reject_status=False):
        self.calls = []
        self.reject_status = reject_status

    def invoke(self, messages):
        self.calls.append(messages)
        if len(self.calls) == 1:
            context = json.loads(messages[1]["content"])
            plan = dict(context["primary_execution_plan"])
            plan["signal_definition"] = (
                "Use a new trailing-window signal and hold-off threshold "
                "strictly before the trade date, reflecting human feedback: "
                + context["reviewer_feedback"][:100]
            )
            if self.reject_status:
                plan["implementation_status"] = "implemented"
                plan["executable_strategy_id"] = "made_up_strategy"
            return SimpleNamespace(content=json.dumps({
                "candidate_id": context["research_decision"]["primary_candidate_id"],
                "revised_summary": (
                    "Concrete fee-aware plan with prior-day lagged signals, "
                    "gold market closure handling and chronological validation; "
                    "the previous research rules are superseded by this revision."
                ),
                "revised_execution_plan": plan,
                "changes_made": (
                    "Changed the actual trading signal to address human feedback "
                    "and preserved the unimplemented status for Sprint B."
                ),
                "next_tests": ["Compare costs in a held-out period"],
                "remaining_risks": ["Past correlations are descriptive only"],
            }), provider="mock", model="reviser")
        return SimpleNamespace(
            content="Independent critic: verify the revised timing convention and no-trade threshold on an unseen period; it remains a research hypothesis.",
            provider="mock", model="reviser",
        )


def test_v2_human_feedback_revises_execution_plan_over_two_rounds():
    from agents.research_revision import revise_with_feedback

    current = _proposal()
    first_feedback = "Please change the transaction timing to avoid close-price lookahead."
    second_feedback = "Please add stricter cash and risk limits when markets are volatile."
    records = []
    for feedback in (first_feedback, second_feedback):
        mock = FakeHumanReviser()
        newer, history = revise_with_feedback(
            proposal=current,
            feedback=feedback,
            problem_specification={"title": "2022 MCM C", "constraints": [
                {"statement": "Gold market closed on weekends"},
            ]},
            eda_report=_evidence(),
            settings=get_settings(), llm=mock, language="en",
        )
        assert len(mock.calls) == 2
        assert newer.proposal_id != current.proposal_id
        assert newer.research_decision.primary_candidate_id == current.research_decision.primary_candidate_id
        assert newer.candidates[0].execution_plan != current.candidates[0].execution_plan
        assert newer.candidates[0].execution_plan.implementation_status == "needs_implementation"
        assert history["feedback"] == feedback
        assert history["before"] != history["after"]
        records.append(history)
        current = newer
    assert len({r["new_proposal_id"] for r in records}) == 2
    rejected = FakeHumanReviser(reject_status=True)
    with pytest.raises(ValueError, match="cannot claim implementation"):
        revise_with_feedback(
            proposal=current, feedback="Please simulate the unimplemented model as if done.",
            problem_specification={"title": "2022 MCM C"}, eda_report=_evidence(),
            settings=get_settings(), llm=rejected,
        )
    assert len(rejected.calls) == 1
