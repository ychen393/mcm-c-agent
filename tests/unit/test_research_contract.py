"""Phase 5 research / H1 Pydantic contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.research import (
    CandidateMethod,
    CritiqueFinding,
    DebateCritique,
    H1Decision,
    HypothesisItem,
    ModelingGateStatus,
    ProvenanceRef,
    ResearchProposal,
    ValidationPlanItem,
)


def _candidate(**overrides) -> CandidateMethod:
    payload = {
        "candidate_id": "cand_example",
        "title": "Cost-aware portfolio baseline",
        "summary": "Use transaction-cost aware rebalancing on gold/bitcoin series.",
        "method_family": "cost_aware_trading",
        "hypotheses": [
            {
                "hypothesis_id": "hyp_example",
                "statement": "Cost-aware rules reduce turnover drag versus naive daily trading.",
                "related_question_ids": ["rq_daily_strategy"],
                "provenance": [
                    {
                        "kind": "problem_specification",
                        "ref_id": "rq_daily_strategy",
                        "summary": "Daily trading strategy research question.",
                    }
                ],
            }
        ],
        "data_needs": [
            {
                "need_id": "dn_example",
                "description": "Daily gold and bitcoin price series.",
                "required": True,
                "satisfied": True,
            }
        ],
        "validation_plan": [
            {
                "plan_id": "vp_example",
                "description": "Hold out the final year for out-of-sample checks.",
                "method": "holdout",
            }
        ],
        "invented_sources": False,
    }
    payload.update(overrides)
    return CandidateMethod.model_validate(payload)


def test_candidate_rejects_invented_sources():
    with pytest.raises(ValidationError):
        _candidate(invented_sources=True)


def test_proposal_requires_recommended_in_candidates():
    with pytest.raises(ValidationError):
        ResearchProposal.model_validate(
            {
                "proposal_id": "prop_example",
                "candidates": [_candidate().model_dump(mode="json")],
                "recommended_candidate_id": "cand_missing",
            }
        )


def test_proposal_happy_path():
    cand = _candidate()
    proposal = ResearchProposal.model_validate(
        {
            "proposal_id": "prop_example",
            "candidates": [cand.model_dump(mode="json")],
            "recommended_candidate_id": cand.candidate_id,
            "invented_sources": False,
        }
    )
    assert proposal.recommended_candidate_id == "cand_example"


def test_critique_rejects_invented_finding():
    with pytest.raises(ValidationError):
        CritiqueFinding.model_validate(
            {
                "finding_id": "cf_bad",
                "kind": "evidence_gap",
                "statement": "Invented citation must be rejected.",
                "invented_source": True,
            }
        )


def test_critique_blocking_count_derived():
    critique = DebateCritique.model_validate(
        {
            "critique_id": "crit_example",
            "proposal_id": "prop_example",
            "findings": [
                {
                    "finding_id": "cf_one",
                    "kind": "evidence_gap",
                    "severity": "blocking",
                    "statement": "Missing literature grounding for method family.",
                },
                {
                    "finding_id": "cf_two",
                    "kind": "other",
                    "severity": "info",
                    "statement": "Minor wording issue in strengths list.",
                },
            ],
            "blocking_count": 99,
        }
    )
    assert critique.blocking_count == 1


def test_h1_rejects_auto_approve():
    with pytest.raises(ValidationError):
        H1Decision.model_validate(
            {
                "decision_id": "h1d_bad",
                "status": "approved",
                "proposal_id": "prop_example",
                "selected_candidate_id": "cand_example",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )


def test_h1_approve_requires_candidate_and_timestamp():
    with pytest.raises(ValidationError):
        H1Decision.model_validate(
            {
                "decision_id": "h1d_incomplete",
                "status": "approved",
                "proposal_id": "prop_example",
                "decided_by": "human",
                "auto_approved": False,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )


def test_modeling_gate_blocks_without_approval():
    gate = ModelingGateStatus.model_validate(
        {
            "modeling_allowed": False,
            "h1_status": "pending",
            "reason": "h1_pending",
            "message": "H1 is pending human Approve / Request-revision — modeling blocked.",
        }
    )
    assert gate.modeling_allowed is False
    with pytest.raises(ValidationError):
        ModelingGateStatus.model_validate(
            {
                "modeling_allowed": True,
                "h1_status": "pending",
                "reason": "h1_approved",
                "message": "Should fail consistency checks.",
            }
        )


def test_hypothesis_provenance_shape():
    hyp = HypothesisItem.model_validate(
        {
            "hypothesis_id": "hyp_x",
            "statement": "A testable claim about rebalancing thresholds.",
            "provenance": [
                ProvenanceRef(
                    kind="rule_based",
                    ref_id="rule1",
                    summary="Deterministic synthesis provenance.",
                ).model_dump(mode="json")
            ],
        }
    )
    assert hyp.provenance[0].kind == "rule_based"
    plan = ValidationPlanItem.model_validate(
        {
            "plan_id": "vp_x",
            "description": "Sensitivity on transaction costs.",
            "method": "sensitivity",
        }
    )
    assert plan.method == "sensitivity"
