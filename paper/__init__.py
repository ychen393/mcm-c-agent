"""Paper Planner / LaTeX / Reviewer package (Phase 8).

``gate`` enforces H2-approved paper generation and blocks Phase 9 E2E until
human H3 approval. ``planner`` / ``latex`` / ``reviewer`` provide the CI-safe
deterministic path for the 2022 MCM C fixture outline.
"""

from paper.gate import (
    assert_e2e_allowed,
    assert_paper_allowed,
    e2e_allowed,
    e2e_gate_status,
    paper_allowed,
    paper_generation_gate_status,
    read_h3_status,
)
from paper.latex import build_latex_bundle, emit_bib_source, emit_tex_source
from paper.planner import build_fixture_outline
from paper.reviewer import review_paper_outline

__all__ = [
    "assert_e2e_allowed",
    "assert_paper_allowed",
    "build_fixture_outline",
    "build_latex_bundle",
    "e2e_allowed",
    "e2e_gate_status",
    "emit_bib_source",
    "emit_tex_source",
    "paper_allowed",
    "paper_generation_gate_status",
    "read_h3_status",
    "review_paper_outline",
]
