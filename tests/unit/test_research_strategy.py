"""Phase 5 Research Strategy agent tests (deterministic / CI-safe)."""

from __future__ import annotations

from agents.literature_evidence import gather_literature_evidence
from agents.problem_analyst import analyze_problem
from agents.research_strategy import research_strategy_status, synthesize_research_proposal
from tools.problem_spec_2022_c import load_2022_c_fixture


def test_status_advertises_h1_without_auto_approve():
    status = research_strategy_status()
    assert status["implemented"] is True
    assert status["h1_available"] is True
    assert status["h1_auto_approve"] is False
    assert status["modeling_requires_h1"] is True
    assert status["llm_default"] is False


def test_synthesize_from_2022_c_fixture_deterministic():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    evidence = gather_literature_evidence(problem_specification=spec, use_live=False)
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        evidence_report=evidence,
        use_llm=False,
    )
    assert proposal.strategy == "deterministic_rules"
    assert proposal.llm_enabled is False
    assert proposal.invented_sources is False
    assert proposal.problem_specification_present is True
    assert proposal.evidence_present is True
    assert len(proposal.candidates) >= 1
    assert proposal.recommended_candidate_id in {
        c.candidate_id for c in proposal.candidates
    }
    for cand in proposal.candidates:
        assert cand.invented_sources is False
        assert cand.validation_plan
        assert cand.hypotheses or cand.data_needs


def test_synthesize_without_spec_emits_baseline_and_open_question():
    proposal = synthesize_research_proposal(use_llm=False)
    assert proposal.problem_specification_present is False
    assert len(proposal.candidates) == 1
    assert any("ProblemSpecification" in q for q in proposal.open_questions)


def test_llm_flag_records_unavailable_stub_without_inventing():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        use_llm=True,
    )
    assert proposal.llm_enabled is True
    assert proposal.llm_attempted is True
    assert proposal.llm_note
    assert proposal.invented_sources is False
    assert proposal.strategy == "hybrid"
