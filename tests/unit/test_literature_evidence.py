"""Phase 4 Literature & Evidence Agent — offline fixture path (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.literature_evidence import (
    LIVE_UNAVAILABLE_NOTE,
    PROMPT_VERSION,
    attempt_live_retrieval,
    gather_literature_evidence,
)
from agents.problem_analyst import analyze_problem
from agents.research_strategy_stub import research_strategy_status
from schemas.eda_plan import ProblemAwareEDAPlan
from schemas.evidence import LiteratureEvidenceReport
from tools.literature_corpus import (
    DEFAULT_CORPUS_PATH,
    corpus_source_ids,
    load_fixture_corpus,
    search_fixture_sources,
)
from tools.problem_spec_2022_c import load_2022_c_fixture

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def fixture_text() -> str:
    return load_2022_c_fixture()


@pytest.fixture(scope="module")
def problem_spec(fixture_text: str):
    return analyze_problem(fixture_text, use_llm=False)


def test_fixture_corpus_loads_and_has_local_snippets():
    corpus = load_fixture_corpus()
    assert corpus["corpus_id"]
    assert DEFAULT_CORPUS_PATH.is_file()
    ids = corpus_source_ids(corpus)
    assert "fx_txn_cost_portfolio" in ids
    assert "fx_past_price_only" in ids
    assert "fx_calendar_assets" in ids
    for source in corpus["sources"]:
        assert source["source_type"] == "fixture_stub"
        path = REPO / source["snippet_file"]
        assert path.is_file(), source["snippet_file"]
        assert "FIXTURE" in path.read_text(encoding="utf-8")


def test_search_ranks_transaction_cost_theme():
    hits = search_fixture_sources(
        query_text="transaction costs gold bitcoin portfolio rebalancing",
        research_question_ids=["rq_daily_strategy"],
        limit=3,
    )
    assert hits
    assert hits[0]["source_id"] in corpus_source_ids()


def test_gather_evidence_grounded_to_2022_c(problem_spec):
    report = gather_literature_evidence(
        problem_specification=problem_spec,
        use_live=False,
    )
    assert isinstance(report, LiteratureEvidenceReport)
    assert report.strategy == "deterministic_fixture"
    assert report.problem_specification_present is True
    assert report.invented_sources is False
    assert report.agent_prompt_version == PROMPT_VERSION
    assert report.cards
    assert report.problem_id == "2022_mcm_c"
    allowed = corpus_source_ids()
    for card in report.cards:
        assert card.source.source_id in allowed
        assert card.invented is False
        assert card.source.source_type == "fixture_stub"
        assert card.verification_status in {
            "verified_fixture",
            "unverified",
            "insufficient_evidence",
            "unknown",
            "rejected",
        }
        if card.verification_status == "verified_fixture":
            assert card.locator_status == "fixture_local"
            assert card.snippets
        assert card.citation.citation_key
        assert card.grounding


def test_gather_evidence_with_eda_context(problem_spec):
    plan = ProblemAwareEDAPlan(
        has_problem_specification=True,
        problem_id="2022_mcm_c",
        analysis_notes=["Respect gold open-day calendar when profiling date keys."],
        suggested_relationships=[],
        must_not=["Do not auto-merge gold and bitcoin."],
    )
    eda_report = {
        "mode": "independent_multi",
        "datasets": [
            {"warnings": ["Date frequency differs across uploaded files."]},
        ],
        "relationships": {"limitations": ["Join not confirmed."]},
    }
    report = gather_literature_evidence(
        problem_specification=problem_spec,
        eda_plan=plan,
        eda_report=eda_report,
        use_live=False,
    )
    assert report.eda_context_present is True
    assert any("EDA" in note or "eda" in note.lower() for note in report.analysis_notes)


def test_missing_problem_spec_marks_unknown_gap():
    report = gather_literature_evidence(problem_specification=None, use_live=False)
    assert report.problem_specification_present is False
    assert any(gap.target_id == "problem_specification" for gap in report.gaps)
    assert any(gap.sufficiency in {"unknown", "insufficient"} for gap in report.gaps)


def test_live_retrieval_stub_does_not_invent():
    attempted, note, cards = attempt_live_retrieval(enabled=True)
    assert attempted is True
    assert note == LIVE_UNAVAILABLE_NOTE
    assert cards == []
    report = gather_literature_evidence(
        problem_specification={"problem_id": "2022_mcm_c", "title": "Trading Strategies", "research_questions": [
            {
                "id": "rq_daily_strategy",
                "statement": "Develop a daily trading strategy for gold and bitcoin.",
                "provenance": "official",
                "source_excerpt": "develop a daily trading strategy",
            }
        ]},
        use_live=True,
    )
    assert report.live_retrieval_attempted is True
    assert report.live_retrieval_note
    assert report.invented_sources is False
    for card in report.cards:
        assert card.source.source_id in corpus_source_ids()


def test_phase5_status_available_without_auto_approve():
    status = research_strategy_status()
    assert status["implemented"] is True
    assert status["h1_available"] is True
    assert status["h1_auto_approve"] is False
    assert status["modeling_requires_h1"] is True
