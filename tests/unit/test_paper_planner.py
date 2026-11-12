"""Phase 8 deterministic planner / latex / reviewer (offline)."""

from __future__ import annotations

from agents.literature_evidence import gather_literature_evidence
from agents.problem_analyst import analyze_problem
from paper.latex import build_latex_bundle, emit_bib_source, latex_looks_structured
from paper.planner import build_fixture_outline
from paper.reviewer import review_paper_outline
from tools.problem_spec_2022_c import load_2022_c_fixture


def _state_with_evidence():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    evidence = gather_literature_evidence(
        problem_specification=spec,
        use_live=False,
    )
    return {
        "problem_specification": spec.model_dump(mode="json"),
        "evidence_report": evidence.model_dump(mode="json"),
        "validation_report": {
            "report_id": "vrep_fixture",
            "baseline_run_id": "erun_fixture",
            "proposal_id": "prop_fixture",
            "scenarios": [{"scenario_id": "scn_a"}],
        },
        "research_proposal": {"proposal_id": "prop_fixture"},
        "decision_report": {
            "experiment": {
                "report_id": "erep_fixture",
                "latest_run_id": "erun_fixture",
            }
        },
        "approval_status": {"h2": "approved"},
    }, spec


def test_fixture_outline_grounded_and_has_required_sections():
    state, spec = _state_with_evidence()
    outline = build_fixture_outline(
        state=state,
        problem_specification=spec,
        llm_enabled=False,
    )
    assert outline.invented_citations is False
    assert outline.strategy == "deterministic_fixture"
    kinds = {s.kind for s in outline.sections}
    for required in (
        "abstract",
        "introduction",
        "problem",
        "methods",
        "results",
        "validation",
        "conclusion",
        "references",
    ):
        assert required in kinds
    assert outline.bib_entries, "expected grounded bib from fixture evidence"
    assert all(not e.invented and e.grounded for e in outline.bib_entries)
    assert outline.validation_report_id == "vrep_fixture"
    assert outline.baseline_run_id == "erun_fixture"


def test_outline_without_evidence_records_citation_gaps():
    outline = build_fixture_outline(
        state={
            "problem_specification": {"problem_id": "2022_mcm_c"},
            "approval_status": {"h2": "approved"},
        },
        llm_enabled=False,
    )
    assert outline.bib_entries == []
    assert outline.citation_gaps
    assert outline.invented_citations is False


def test_latex_emission_offline_and_soft_compile():
    state, spec = _state_with_evidence()
    outline = build_fixture_outline(state=state, problem_specification=spec)
    bundle = build_latex_bundle(outline, attempt_compile=True)
    assert latex_looks_structured(bundle.tex_source)
    assert "\\begin{document}" in bundle.tex_source
    assert bundle.compile_attempted is True
    # Soft-fail or success both OK — TeX may be absent in CI.
    assert bundle.compile_ok in {True, False}
    assert bundle.compile_note
    bib = emit_bib_source(outline)
    for entry in outline.bib_entries:
        assert entry.citation_key in bib


def test_reviewer_pass_or_warn_on_fixture_outline():
    state, spec = _state_with_evidence()
    outline = build_fixture_outline(state=state, problem_specification=spec)
    latex = build_latex_bundle(outline, attempt_compile=False)
    review = review_paper_outline(outline, latex=latex)
    assert review.invented_citations is False
    assert review.structure_ok is True
    assert review.topic_coverage_ok is True
    assert review.overall_status in {"pass", "warn"}
