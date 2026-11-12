"""Paper Planner / LaTeX / Reviewer Agent (Phase 8).

Default path is CI-safe deterministic outline + offline LaTeX/BibTeX emission
and a light reviewer checklist. Runs are refused unless ResearchState shows
human H2 approval. Optional LLM outline stays a non-executing stub. H3 is
never auto-approved; Phase 9 E2E stays blocked until human H3.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from core.config import Settings, get_settings
from paper.gate import assert_paper_allowed, paper_generation_gate_status
from paper.latex import build_latex_bundle
from paper.planner import LLM_UNAVAILABLE_NOTE, PROMPT_VERSION, build_fixture_outline
from paper.reviewer import review_paper_outline
from schemas.paper import PaperPackage
from schemas.problem_specification import ProblemSpecification


def _llm_enabled(settings: Settings | None, use_llm: bool | None) -> bool:
    if use_llm is not None:
        return bool(use_llm)
    if settings is not None:
        return bool(settings.paper_use_llm)
    env = os.getenv("PAPER_USE_LLM", "").strip().lower()
    return env in {"1", "true", "yes", "on"}


def paper_planner_status(settings: Settings | None = None) -> dict[str, Any]:
    """Status advertisement for UI / tests."""
    cfg = settings or get_settings()
    return {
        "phase": 8,
        "agent": "paper_planner",
        "prompt_version": PROMPT_VERSION,
        "default_strategy": "deterministic_fixture",
        "invented_citations": False,
        "h1_auto_approve": False,
        "h2_auto_approve": False,
        "h3_auto_approve": False,
        "requires_h2_approved": True,
        "e2e_requires_h3_approved": True,
        "pdf_compile_required_for_ci": False,
        "llm_outline_default": bool(cfg.paper_use_llm),
        "llm_outline_executes_live_calls": False,
        "llm_note": LLM_UNAVAILABLE_NOTE,
    }


def run_paper_planner(
    *,
    state: dict[str, Any] | None,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    use_llm: bool | None = None,
    attempt_pdf_compile: bool = False,
    settings: Settings | None = None,
) -> PaperPackage:
    """Build outline + latex + review when H2 allows; else PermissionError."""
    assert_paper_allowed(state)
    gate = paper_generation_gate_status(state)

    cfg = settings or get_settings()
    llm = _llm_enabled(cfg, use_llm)

    spec = problem_specification
    if spec is None and state:
        spec = state.get("problem_specification")

    outline = build_fixture_outline(
        state=state,
        problem_specification=spec,
        llm_enabled=llm,
    )
    latex = build_latex_bundle(outline, attempt_compile=attempt_pdf_compile)
    review = review_paper_outline(outline, latex=latex)

    notes = list(outline.analysis_notes)
    notes.append(f"paper_gate.reason={gate.reason}")
    notes.append(f"review.overall={review.overall_status}")
    outline = outline.model_copy(update={"analysis_notes": notes[:32]})

    digest = hashlib.sha256(
        f"{outline.outline_id}|{latex.bundle_id}|{review.review_id}".encode()
    ).hexdigest()[:10]
    return PaperPackage(
        package_id=f"ppkg_{digest}",
        outline=outline,
        latex=latex,
        review=review,
        h2_approved=True,
        paper_allowed=True,
        invented_citations=False,
    )
