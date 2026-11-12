"""Shared Streamlit session cache clears for derived Phase 2–8 products.

Foundation rebuild, reopen, continue, and history load must all drop these keys so
orphan UI state cannot outrank a loaded/cleared ResearchState (Phase 2 P1 class;
Phase 3 P1 for EDA plan / integration preview; Phase 4 literature evidence;
Phase 5 research proposal / H1 draft caches; Phase 6 modeling experiment drafts;
Phase 7 validation / H2 draft caches; Phase 8 paper / H3 draft caches).
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from app.problem_analyst_panel import clear_problem_specification_cache

PHASE3_EDA_SESSION_KEYS: tuple[str, ...] = (
    "problem_aware_eda_plan",
    "integration_preview_confirmation",
    "integration_preview_result",
    "integration_preview_selection",
)

PHASE4_LITERATURE_SESSION_KEYS: tuple[str, ...] = (
    "literature_evidence_report",
)

PHASE5_RESEARCH_SESSION_KEYS: tuple[str, ...] = (
    "research_proposal_draft",
    "debate_critique_draft",
)

PHASE6_MODELING_SESSION_KEYS: tuple[str, ...] = (
    "modeling_experiment_draft",
)

PHASE7_VALIDATION_SESSION_KEYS: tuple[str, ...] = (
    "validation_sensitivity_draft",
)

PHASE8_PAPER_SESSION_KEYS: tuple[str, ...] = (
    "paper_planner_draft",
)


def clear_phase3_eda_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop problem-aware plan and integration-preview session caches."""
    state = st.session_state if session_state is None else session_state
    for key in PHASE3_EDA_SESSION_KEYS:
        state.pop(key, None)


def clear_phase4_literature_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop literature evidence session caches."""
    state = st.session_state if session_state is None else session_state
    for key in PHASE4_LITERATURE_SESSION_KEYS:
        state.pop(key, None)


def clear_phase5_research_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop research proposal / Debate / H1 draft session caches."""
    state = st.session_state if session_state is None else session_state
    for key in PHASE5_RESEARCH_SESSION_KEYS:
        state.pop(key, None)


def clear_phase6_modeling_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop modeling experiment draft session caches."""
    state = st.session_state if session_state is None else session_state
    for key in PHASE6_MODELING_SESSION_KEYS:
        state.pop(key, None)


def clear_phase7_validation_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop validation / H2 draft session caches."""
    state = st.session_state if session_state is None else session_state
    for key in PHASE7_VALIDATION_SESSION_KEYS:
        state.pop(key, None)


def clear_phase8_paper_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop paper / H3 draft session caches."""
    state = st.session_state if session_state is None else session_state
    for key in PHASE8_PAPER_SESSION_KEYS:
        state.pop(key, None)


def clear_derived_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Clear ProblemSpecification + Phase 3–8 derived UI caches."""
    clear_problem_specification_cache(session_state)
    clear_phase3_eda_session_caches(session_state)
    clear_phase4_literature_session_caches(session_state)
    clear_phase5_research_session_caches(session_state)
    clear_phase6_modeling_session_caches(session_state)
    clear_phase7_validation_session_caches(session_state)
    clear_phase8_paper_session_caches(session_state)
