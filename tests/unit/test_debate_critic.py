"""Phase 5 Debate / Critic agent tests (deterministic / CI-safe)."""

from __future__ import annotations

from agents.debate_critic import critique_research_proposal
from agents.literature_evidence import gather_literature_evidence
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from tools.problem_spec_2022_c import load_2022_c_fixture


def test_critique_surfaces_evidence_and_assumption_findings():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    evidence = gather_literature_evidence(problem_specification=spec, use_live=False)
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        evidence_report=evidence,
        use_llm=False,
    )
    critique = critique_research_proposal(
        proposal=proposal,
        problem_specification=spec,
        evidence_report=evidence,
        use_llm=False,
    )
    assert critique.invented_sources is False
    assert critique.proposal_id == proposal.proposal_id
    assert critique.strategy == "deterministic_rules"
    kinds = {f.kind for f in critique.findings}
    # 2022 C fixture has assumptions_to_validate and often evidence gaps.
    assert "weak_assumption" in kinds or "evidence_gap" in kinds or "validation_gap" in kinds
    for finding in critique.findings:
        assert finding.invented_source is False


def test_critique_without_evidence_marks_high_severity_gap():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    critique = critique_research_proposal(
        proposal=proposal,
        problem_specification=spec,
        evidence_report=None,
        use_llm=False,
    )
    assert any(
        f.kind == "evidence_gap" and f.severity in {"high", "blocking"}
        for f in critique.findings
    )


def test_critique_llm_flag_is_non_inventing_stub():
    proposal = synthesize_research_proposal(use_llm=False)
    critique = critique_research_proposal(proposal=proposal, use_llm=True)
    assert critique.llm_attempted is True
    assert critique.llm_note
    assert critique.invented_sources is False
