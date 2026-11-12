"""Phase 8 paper / LaTeX / H3 contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.paper import (
    BibEntry,
    E2EGateStatus,
    H3Decision,
    PaperOutline,
    PaperSection,
    PaperGenerationGateStatus,
)


def _section(**overrides) -> PaperSection:
    base = dict(
        section_id="sec_abstract",
        kind="abstract",
        title="Abstract",
        summary="Summary of the trading strategy and results.",
        order=0,
        required=True,
    )
    base.update(overrides)
    return PaperSection(**base)


def _outline(**overrides) -> PaperOutline:
    base = dict(
        outline_id="pout_x",
        h2_approved=True,
        paper_allowed=True,
        title="Trading Strategies for Gold and Bitcoin",
        sections=[
            _section(),
            _section(
                section_id="sec_methods",
                kind="methods",
                title="Methodology",
                summary="Cost-aware rebalancing method.",
                order=1,
            ),
        ],
        bib_entries=[],
        invented_citations=False,
    )
    base.update(overrides)
    return PaperOutline(**base)


def test_outline_requires_h2_and_sections():
    with pytest.raises(ValidationError):
        _outline(h2_approved=False)
    with pytest.raises(ValidationError):
        _outline(sections=[])


def test_bib_rejects_invented():
    with pytest.raises(ValidationError):
        BibEntry(
            citation_key="Fake2022",
            title="Invented paper",
            invented=True,
            grounded=True,
        )
    with pytest.raises(ValidationError):
        BibEntry(
            citation_key="Ungrounded2022",
            title="Ungrounded paper",
            invented=False,
            grounded=False,
        )


def test_outline_rejects_unknown_cite_without_gap():
    with pytest.raises(ValidationError):
        _outline(
            sections=[
                _section(citation_keys=["MissingKey2022"]),
            ],
            bib_entries=[],
            citation_gaps=[],
        )


def test_outline_allows_cite_listed_as_gap():
    outline = _outline(
        sections=[_section(citation_keys=["MissingKey2022"])],
        citation_gaps=["MissingKey2022"],
    )
    assert "MissingKey2022" in outline.citation_gaps


def test_h3_never_auto_approved():
    with pytest.raises(ValidationError):
        H3Decision(
            decision_id="h3d_x",
            status="approved",
            package_id="ppkg_x",
            auto_approved=True,
            decided_by="human",
            decided_at_utc="2026-01-01T00:00:00Z",
        )
    with pytest.raises(ValidationError):
        H3Decision(
            decision_id="h3d_x",
            status="approved",
            package_id="ppkg_x",
            auto_approved=False,
            decided_by="human",
            # missing decided_at_utc
        )


def test_h3_human_approved_ok():
    decision = H3Decision(
        decision_id="h3d_ok",
        status="approved",
        package_id="ppkg_x",
        auto_approved=False,
        decided_by="human",
        decided_at_utc="2026-01-01T00:00:00Z",
    )
    assert decision.auto_approved is False


def test_paper_and_e2e_gates_consistent():
    with pytest.raises(ValidationError):
        PaperGenerationGateStatus(
            paper_allowed=True,
            h2_status="pending",
            reason="h2_approved",
            message="bad",
        )
    with pytest.raises(ValidationError):
        E2EGateStatus(
            e2e_allowed=True,
            h3_status="pending",
            reason="h3_approved",
            message="bad",
        )
    ok = E2EGateStatus(
        e2e_allowed=True,
        h3_status="approved",
        reason="h3_approved",
        message="H3 approved by a human.",
    )
    assert ok.e2e_allowed is True
