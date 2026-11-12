"""Shared Streamlit session cache clears for derived Phase 2 / 3 / 4 products.

Foundation rebuild, reopen, continue, and history load must all drop these keys so
orphan UI state cannot outrank a loaded/cleared ResearchState (Phase 2 P1 class;
Phase 3 P1 for EDA plan / integration preview; Phase 4 literature evidence).
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


def clear_derived_session_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Clear ProblemSpecification + Phase 3 EDA + Phase 4 literature caches."""
    clear_problem_specification_cache(session_state)
    clear_phase3_eda_session_caches(session_state)
    clear_phase4_literature_session_caches(session_state)
