"""Streamlit panel: run Problem Analyst and show ProblemSpecification."""
from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from agents.problem_analyst import analyze_problem
from core.config import Settings
from tools.problem_spec_2022_c import acceptance_checklist_2022_c

PROBLEM_SPEC_SESSION_KEY = "problem_specification"


def clear_problem_specification_cache(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop the orphan UI cache. Call on foundation rebuild / reopen / continue / history."""
    state = st.session_state if session_state is None else session_state
    state.pop(PROBLEM_SPEC_SESSION_KEY, None)


def resolve_displayed_problem_specification(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded ResearchState over an orphan session cache.

    When a foundation ``recorded_state`` exists, an empty/cleared
    ``problem_specification`` wins over any leftover session cache (inputs
    changed, reopen, continue, or history load). The session cache is only
    used before Initialize (analyze-before-init), when there is no recorded run.
    """
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        existing = recorded_state.get("problem_specification")
        if isinstance(existing, dict) and existing:
            return existing
        # Recorded run is authoritative: cleared/empty means do not show a stale cache.
        return None
    cached = state.get(PROBLEM_SPEC_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def render_problem_analyst_panel(
    problem_text: str,
    *,
    settings: Settings,
    recorded_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Render analyst controls. Returns the latest spec dict if one is available."""
    st.subheader("Problem Analyst")
    st.caption(
        "Produces a validated ProblemSpecification (Pydantic). "
        "CI uses the deterministic 2022 MCM C fixture path; "
        "optional LLM extraction is off unless PROBLEM_ANALYST_USE_LLM is enabled. "
        "Displayed specs follow the recorded run; the session cache is cleared when "
        "inputs rebuild or a run is reopened/continued."
    )

    use_llm = st.checkbox(
        "Use LLM analyst (optional)",
        value=bool(settings.problem_analyst_use_llm),
        help=(
            "Default off. When on, output still must pass ProblemSpecification "
            "validation with one repair attempt."
        ),
        key="problem_analyst_use_llm_ui",
    )

    col_a, col_b = st.columns([1, 2])
    with col_a:
        run = st.button("Analyze problem", type="primary", key="run_problem_analyst")
    with col_b:
        st.caption(
            f"Configured flag PROBLEM_ANALYST_USE_LLM={settings.problem_analyst_use_llm} · "
            f"UI override use_llm={use_llm}"
        )

    spec_dict = resolve_displayed_problem_specification(recorded_state)

    if run:
        if not problem_text.strip():
            st.error("Paste an MCM problem statement before running the Problem Analyst.")
        else:
            try:
                spec = analyze_problem(
                    problem_text,
                    use_llm=use_llm,
                    settings=settings,
                )
            except Exception as exc:
                st.error(f"Problem Analyst failed: {type(exc).__name__}: {exc}")
            else:
                spec_dict = spec.model_dump(mode="json")
                st.session_state[PROBLEM_SPEC_SESSION_KEY] = spec_dict
                if st.session_state.get("last_run") is not None:
                    updated = dict(st.session_state["last_run"])
                    updated["problem_specification"] = spec_dict
                    st.session_state["last_run"] = updated
                st.success(
                    f"Validated ProblemSpecification · problem_id={spec.problem_id} · "
                    f"strategy={spec.strategy}"
                )
                if spec.problem_id == "2022_mcm_c":
                    checks = acceptance_checklist_2022_c(spec)
                    failed = [name for name, ok in checks.items() if not ok]
                    if failed:
                        st.warning(
                            "2022 C acceptance checklist incomplete: " + ", ".join(failed)
                        )
                    else:
                        st.info("2022 C acceptance checklist: all required facts present.")

    if spec_dict:
        st.markdown("**Structured ProblemSpecification**")
        st.json(spec_dict)
    else:
        st.info("No ProblemSpecification yet. Analyze the problem statement to generate one.")

    return spec_dict
