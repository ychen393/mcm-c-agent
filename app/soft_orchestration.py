"""UX-D soft orchestration: guided next step + soft panel locks.

Product UX only — does **not** auto-run research agents, does **not**
auto-approve H1/H2/H3, and does **not** build a LangGraph Orchestrator.
Power users can unlock all panels via session override.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import streamlit as st

from app.i18n import t
from app.progress_chrome import (
    STEP_ORDER,
    StepId,
    completed_steps_from_state,
    current_step_from_state,
    step_label,
)
from modeling.gate import modeling_allowed, read_h1_status
from paper.gate import e2e_allowed, read_h3_status
from validation.gate import has_experiment_results, paper_allowed, read_h2_status

PanelId = Literal[
    "problem",
    "eda",
    "literature",
    "h1",
    "modeling",
    "h2",
    "paper",
]

PANEL_ORDER: tuple[PanelId, ...] = (
    "problem",
    "eda",
    "literature",
    "h1",
    "modeling",
    "h2",
    "paper",
)

OVERRIDE_KEY = "ux_soft_unlock_all"
FOCUS_KEY = "ux_soft_focus_panel"

ActionKind = Literal["initialize", "run_panel", "human_gate", "complete"]


@dataclass(frozen=True)
class NextStepGuide:
    """Human-facing guided next action derived from ResearchState."""

    step_id: StepId
    panel_id: PanelId | None
    action_kind: ActionKind
    gate_name: str | None
    title_key: str
    detail_key: str
    cta_key: str


def _nonempty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _project_initialized(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    phases = state.get("workspace_phases") or {}
    if isinstance(phases, dict) and phases.get("project_initialized") == "yes":
        return True
    return bool(state.get("run_id") or state.get("project_id"))


def _has_problem_spec(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    return _nonempty_dict(state.get("problem_specification"))


def _has_eda(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    phases = state.get("workspace_phases") or {}
    if isinstance(phases, dict) and phases.get("independent_eda") == "done":
        return True
    return _nonempty_dict(state.get("eda_report"))


def _has_literature(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    phases = state.get("workspace_phases") or {}
    if isinstance(phases, dict) and phases.get("literature_evidence") in {
        "recorded",
        "done",
    }:
        return True
    return _nonempty_dict(state.get("evidence_report"))


def _has_research_proposal(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    return _nonempty_dict(state.get("research_proposal"))


def _has_validation_report(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    decision = state.get("decision_report") or {}
    if isinstance(decision, dict) and _nonempty_dict(decision.get("validation")):
        return True
    return _nonempty_dict(state.get("validation_report"))


def _has_paper_package(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    phases = state.get("workspace_phases") or {}
    if isinstance(phases, dict) and phases.get("paper_latex") in {
        "recorded",
        "h3_approved",
    }:
        return True
    if _nonempty_dict(state.get("paper_outline")):
        return True
    decision = state.get("decision_report") or {}
    if isinstance(decision, dict) and _nonempty_dict(decision.get("paper")):
        return True
    return False


def soft_unlock_override() -> bool:
    """True when power-user override is on (session sticky)."""
    return bool(st.session_state.get(OVERRIDE_KEY))


def set_soft_unlock_override(value: bool) -> None:
    st.session_state[OVERRIDE_KEY] = bool(value)


def panel_prerequisites_met(panel: PanelId, state: dict[str, Any] | None) -> bool:
    """Whether soft prerequisites for ``panel`` are satisfied (no override)."""
    if panel == "problem":
        return _project_initialized(state)
    if panel == "eda":
        return _has_problem_spec(state)
    if panel == "literature":
        return _has_eda(state)
    if panel == "h1":
        # Linear path prefers literature; allow if proposal already exists
        # (user skipped literature or restored a mid-run).
        return _has_literature(state) or _has_research_proposal(state)
    if panel == "modeling":
        return modeling_allowed(state)
    if panel == "h2":
        return has_experiment_results(state)
    if panel == "paper":
        return paper_allowed(state)
    return False


def panel_is_unlocked(
    panel: PanelId,
    state: dict[str, Any] | None,
    *,
    override: bool | None = None,
) -> bool:
    """Soft unlock: prerequisites or power-user override. Never auto-approves gates."""
    if override if override is not None else soft_unlock_override():
        return True
    return panel_prerequisites_met(panel, state)


def missing_prerequisite_labels(panel: PanelId, state: dict[str, Any] | None) -> tuple[str, ...]:
    """Human labels for unmet soft prerequisites (translated)."""
    labels: list[str] = []
    if panel == "problem" and not _project_initialized(state):
        labels.append(t("soft.prereq.project"))
    elif panel == "eda" and not _has_problem_spec(state):
        labels.append(t("soft.prereq.problem"))
    elif panel == "literature" and not _has_eda(state):
        labels.append(t("soft.prereq.eda"))
    elif panel == "h1" and not (_has_literature(state) or _has_research_proposal(state)):
        labels.append(t("soft.prereq.literature"))
    elif panel == "modeling" and not modeling_allowed(state):
        labels.append(t("soft.prereq.h1"))
    elif panel == "h2" and not has_experiment_results(state):
        labels.append(t("soft.prereq.modeling"))
    elif panel == "paper" and not paper_allowed(state):
        labels.append(t("soft.prereq.h2"))
    return tuple(labels)


def next_step_guide(state: dict[str, Any] | None) -> NextStepGuide:
    """Derive the guided next CTA from project / gate state.

    Human gates (H1/H2/H3) are never auto-approved — CTA only points humans
    at the approval card.
    """
    current = current_step_from_state(state)
    h1 = read_h1_status(state)
    h2 = read_h2_status(state)
    h3 = read_h3_status(state)

    if not _project_initialized(state):
        return NextStepGuide(
            step_id="project",
            panel_id=None,
            action_kind="initialize",
            gate_name=None,
            title_key="soft.next.initialize.title",
            detail_key="soft.next.initialize.detail",
            cta_key="soft.next.initialize.cta",
        )

    if not _has_problem_spec(state):
        return NextStepGuide(
            step_id="problem",
            panel_id="problem",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.problem.title",
            detail_key="soft.next.problem.detail",
            cta_key="soft.next.problem.cta",
        )

    if not _has_eda(state):
        return NextStepGuide(
            step_id="eda",
            panel_id="eda",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.eda.title",
            detail_key="soft.next.eda.detail",
            cta_key="soft.next.eda.cta",
        )

    if not _has_literature(state) and not _has_research_proposal(state):
        return NextStepGuide(
            step_id="literature",
            panel_id="literature",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.literature.title",
            detail_key="soft.next.literature.detail",
            cta_key="soft.next.literature.cta",
        )

    if not _has_research_proposal(state):
        return NextStepGuide(
            step_id="h1",
            panel_id="h1",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.h1_synth.title",
            detail_key="soft.next.h1_synth.detail",
            cta_key="soft.next.h1_synth.cta",
        )

    if h1 in {None, "pending"}:
        return NextStepGuide(
            step_id="h1",
            panel_id="h1",
            action_kind="human_gate",
            gate_name="H1",
            title_key="soft.next.h1_gate.title",
            detail_key="soft.next.h1_gate.detail",
            cta_key="soft.next.h1_gate.cta",
        )

    if h1 == "revision_requested":
        return NextStepGuide(
            step_id="h1",
            panel_id="h1",
            action_kind="human_gate",
            gate_name="H1",
            title_key="soft.next.h1_revision.title",
            detail_key="soft.next.h1_revision.detail",
            cta_key="soft.next.h1_revision.cta",
        )

    if h1 == "rejected":
        return NextStepGuide(
            step_id="h1",
            panel_id="h1",
            action_kind="human_gate",
            gate_name="H1",
            title_key="soft.next.h1_rejected.title",
            detail_key="soft.next.h1_rejected.detail",
            cta_key="soft.next.h1_rejected.cta",
        )

    if not has_experiment_results(state):
        return NextStepGuide(
            step_id="modeling",
            panel_id="modeling",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.modeling.title",
            detail_key="soft.next.modeling.detail",
            cta_key="soft.next.modeling.cta",
        )

    if not _has_validation_report(state) and h2 not in {
        "pending",
        "approved",
        "revision_requested",
        "rejected",
    }:
        return NextStepGuide(
            step_id="h2",
            panel_id="h2",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.h2_run.title",
            detail_key="soft.next.h2_run.detail",
            cta_key="soft.next.h2_run.cta",
        )

    if h2 in {None, "pending"}:
        return NextStepGuide(
            step_id="h2",
            panel_id="h2",
            action_kind="human_gate",
            gate_name="H2",
            title_key="soft.next.h2_gate.title",
            detail_key="soft.next.h2_gate.detail",
            cta_key="soft.next.h2_gate.cta",
        )

    if h2 == "revision_requested":
        return NextStepGuide(
            step_id="h2",
            panel_id="h2",
            action_kind="human_gate",
            gate_name="H2",
            title_key="soft.next.h2_revision.title",
            detail_key="soft.next.h2_revision.detail",
            cta_key="soft.next.h2_revision.cta",
        )

    if h2 == "rejected":
        return NextStepGuide(
            step_id="h2",
            panel_id="h2",
            action_kind="human_gate",
            gate_name="H2",
            title_key="soft.next.h2_rejected.title",
            detail_key="soft.next.h2_rejected.detail",
            cta_key="soft.next.h2_rejected.cta",
        )

    if not _has_paper_package(state):
        return NextStepGuide(
            step_id="paper",
            panel_id="paper",
            action_kind="run_panel",
            gate_name=None,
            title_key="soft.next.paper_gen.title",
            detail_key="soft.next.paper_gen.detail",
            cta_key="soft.next.paper_gen.cta",
        )

    if h3 in {None, "pending"}:
        return NextStepGuide(
            step_id="paper",
            panel_id="paper",
            action_kind="human_gate",
            gate_name="H3",
            title_key="soft.next.h3_gate.title",
            detail_key="soft.next.h3_gate.detail",
            cta_key="soft.next.h3_gate.cta",
        )

    if h3 == "revision_requested":
        return NextStepGuide(
            step_id="paper",
            panel_id="paper",
            action_kind="human_gate",
            gate_name="H3",
            title_key="soft.next.h3_revision.title",
            detail_key="soft.next.h3_revision.detail",
            cta_key="soft.next.h3_revision.cta",
        )

    if h3 == "rejected":
        return NextStepGuide(
            step_id="paper",
            panel_id="paper",
            action_kind="human_gate",
            gate_name="H3",
            title_key="soft.next.h3_rejected.title",
            detail_key="soft.next.h3_rejected.detail",
            cta_key="soft.next.h3_rejected.cta",
        )

    if e2e_allowed(state) or h3 == "approved":
        return NextStepGuide(
            step_id="export",
            panel_id=None,
            action_kind="complete",
            gate_name=None,
            title_key="soft.next.complete.title",
            detail_key="soft.next.complete.detail",
            cta_key="soft.next.complete.cta",
        )

    # Fallback: align with progress chrome current step.
    return NextStepGuide(
        step_id=current,
        panel_id=None,
        action_kind="run_panel",
        gate_name=None,
        title_key="soft.next.fallback.title",
        detail_key="soft.next.fallback.detail",
        cta_key="soft.next.fallback.cta",
    )


def render_locked_panel_stub(panel: PanelId, state: dict[str, Any] | None) -> None:
    """Show panel title + soft-lock notice instead of interactive controls."""
    st.subheader(t(f"soft.panel.{panel}"))
    missing = missing_prerequisite_labels(panel, state)
    missing_text = "; ".join(missing) if missing else t("soft.prereq.unknown")
    st.info(t("soft.lock.message", prereqs=missing_text))
    st.caption(t("soft.lock.caption"))


def render_next_step_guide(state: dict[str, Any] | None) -> NextStepGuide:
    """Render guided next-step chrome; returns the computed guide."""
    guide = next_step_guide(state)
    completed = completed_steps_from_state(state)
    done_n = len(completed)
    total = len(STEP_ORDER)

    st.subheader(t("soft.guide.header"))
    st.caption(t("soft.guide.caption"))

    with st.container(border=True):
        st.markdown(f"**{t(guide.title_key)}**")
        st.write(t(guide.detail_key))
        if guide.action_kind == "human_gate":
            st.warning(t("soft.guide.human_gate_note", gate=guide.gate_name or ""))
        st.caption(
            t(
                "soft.guide.progress_line",
                step=step_label(guide.step_id),
                done=done_n,
                total=total,
            )
        )

        col_cta, col_override = st.columns([2, 2])
        with col_cta:
            if guide.action_kind == "complete":
                st.success(t(guide.cta_key))
            elif guide.panel_id is not None:
                if st.button(t(guide.cta_key), type="primary", key="ux_soft_run_next"):
                    st.session_state[FOCUS_KEY] = guide.panel_id
                    # Soft unlock only the focused next panel path for this run:
                    # keep global override off unless the user checks it.
                    st.info(t("soft.guide.focus_set", panel=t(f"soft.panel.{guide.panel_id}")))
            else:
                st.button(t(guide.cta_key), type="primary", key="ux_soft_run_next")

        with col_override:
            override = st.checkbox(
                t("soft.override.label"),
                value=soft_unlock_override(),
                help=t("soft.override.help"),
                key=OVERRIDE_KEY,
            )
            if override:
                st.caption(t("soft.override.active"))

    focus = st.session_state.get(FOCUS_KEY)
    if isinstance(focus, str) and focus in PANEL_ORDER:
        if panel_is_unlocked(focus, state):  # type: ignore[arg-type]
            st.caption(t("soft.guide.focus_hint", panel=t(f"soft.panel.{focus}")))

    return guide


def focused_panel() -> PanelId | None:
    raw = st.session_state.get(FOCUS_KEY)
    if raw in PANEL_ORDER:
        return raw  # type: ignore[return-value]
    return None
