"""Phase 4 evidence / literature Pydantic contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.evidence import (
    CitationFields,
    EvidenceCard,
    EvidenceGap,
    EvidenceSnippet,
    GroundingLink,
    LiteratureEvidenceReport,
    MethodNote,
    SourceMetadata,
)


def _source(**overrides) -> SourceMetadata:
    payload = {
        "source_id": "fx_example",
        "title": "Fixture example source title",
        "authors": ["MCM C Fixture Corpus"],
        "year": 2022,
        "source_type": "fixture_stub",
        "local_path": "knowledge/fixture_corpus/snippets/fx_txn_cost_portfolio.txt",
        "acquisition_method": "fixture_bundle",
        "review_status": "fixture",
    }
    payload.update(overrides)
    return SourceMetadata.model_validate(payload)


def _card(**overrides) -> EvidenceCard:
    payload = {
        "card_id": "ec_fx_example",
        "source": _source(),
        "snippets": [
            {
                "snippet_id": "sn_fx_example",
                "text": "Fixture quote about transaction costs and rebalancing.",
                "locator": "knowledge/fixture_corpus/snippets/fx_txn_cost_portfolio.txt",
                "is_verbatim_quote": True,
            }
        ],
        "method_notes": [
            {
                "note_id": "mn_example",
                "method_name": "Cost-aware rebalancing",
                "summary": "Trade only when expected edge exceeds proportional costs.",
            }
        ],
        "citation": {
            "citation_key": "FixtureExample2022",
            "citation_type": "fixture",
            "bibtex_fields": {"title": "Fixture example source title", "year": "2022"},
        },
        "grounding": [
            {
                "kind": "research_question",
                "target_id": "rq_daily_strategy",
                "target_statement": "Develop a daily trading strategy.",
                "relevance": "Costs shape daily turnover.",
                "strength": "moderate",
            }
        ],
        "locator_status": "fixture_local",
        "verification_status": "verified_fixture",
        "claim_summary": "Transaction costs should gate rebalancing decisions.",
        "invented": False,
        "tags": ["transaction_costs"],
    }
    payload.update(overrides)
    return EvidenceCard.model_validate(payload)


def test_source_metadata_requires_source_id_pattern():
    with pytest.raises(ValidationError):
        _source(source_id="Bad-Id")


def test_evidence_card_rejects_invented_flag():
    with pytest.raises(ValidationError, match="must not be invented"):
        _card(invented=True)


def test_verified_fixture_requires_fixture_source_and_local_locator():
    with pytest.raises(ValidationError):
        _card(
            source=_source(source_type="open_access"),
            verification_status="verified_fixture",
            locator_status="fixture_local",
        )
    with pytest.raises(ValidationError):
        _card(verification_status="verified_fixture", locator_status="missing")


def test_literature_report_round_trip_and_gap():
    report = LiteratureEvidenceReport(
        problem_id="2022_mcm_c",
        strategy="deterministic_fixture",
        cards=[_card()],
        gaps=[
            EvidenceGap(
                gap_id="gap_rq_sensitivity",
                kind="research_question",
                target_id="rq_sensitivity",
                statement="No fixture coverage for sensitivity analysis evidence.",
                sufficiency="insufficient",
            )
        ],
        grounded_target_ids=["rq_daily_strategy"],
        problem_specification_present=True,
        invented_sources=False,
    )
    dumped = report.model_dump(mode="json")
    again = LiteratureEvidenceReport.model_validate(dumped)
    assert again.cards[0].citation.citation_key == "FixtureExample2022"
    assert again.gaps[0].sufficiency == "insufficient"


def test_report_rejects_invented_sources_flag():
    with pytest.raises(ValidationError, match="must not invent"):
        LiteratureEvidenceReport(invented_sources=True, cards=[_card()])


def test_snippet_span_order():
    with pytest.raises(ValidationError):
        EvidenceSnippet(
            snippet_id="sn_bad",
            text="hello world excerpt",
            char_start=10,
            char_end=2,
        )


def test_citation_and_method_note_bounds():
    cite = CitationFields(
        citation_key="FixtureKey",
        citation_type="fixture",
        bibtex_fields={"title": "x", "note": "CI only"},
    )
    assert cite.bibtex_fields["note"] == "CI only"
    note = MethodNote(
        note_id="mn_ok",
        method_name="Walk-forward",
        summary="Evaluate with past information only.",
    )
    assert "past" in note.summary


def test_grounding_link_kinds():
    link = GroundingLink(
        kind="eda_finding",
        target_id="eda_warn_0",
        relevance="Aligns with an EDA warning about calendars.",
        strength="weak",
    )
    assert link.kind == "eda_finding"
