"""Derive Streamlit progress chrome from ResearchState gates / workspace_phases.

Replaces hardcoded \"Phase 5\" / \"Workflow nodes 2\" / \"Phase 6 not started\" copy.
Does not start agents or change gate logic — presentation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.i18n import t
from modeling.gate import modeling_allowed, read_h1_status
from paper.gate import e2e_allowed, read_h3_status
from validation.gate import has_experiment_results, paper_allowed, read_h2_status

StepId = Literal[
    "project",
    "problem",
    "eda",
    "literature",
    "h1",
    "modeling",
    "h2",
    "paper",
    "export",
]

STEP_ORDER: tuple[StepId, ...] = (
    "project",
    "problem",
    "eda",
    "literature",
    "h1",
    "modeling",
    "h2",
    "paper",
    "export",
)

# English fallbacks kept for imports/tests that still read STEP_LABELS directly.
STEP_LABELS: dict[StepId, str] = {
    "project": "Project",
    "problem": "Problem",
    "eda": "EDA",
    "literature": "Literature",
    "h1": "Research / H1",
    "modeling": "Modeling",
    "h2": "Validation / H2",
    "paper": "Paper / H3",
    "export": "Export",
}

_STEP_I18N: dict[StepId, str] = {
    "project": "progress.step.project",
    "problem": "progress.step.problem",
    "eda": "progress.step.eda",
    "literature": "progress.step.literature",
    "h1": "progress.step.h1",
    "modeling": "progress.step.modeling",
    "h2": "progress.step.h2",
    "paper": "progress.step.paper",
    "export": "progress.step.export",
}


def step_label(step: StepId) -> str:
    return t(_STEP_I18N[step])


@dataclass(frozen=True)
class ProgressChrome:
    """Human-facing progress derived from recorded state."""

    current_step: StepId
    current_label: str
    sidebar_badge: str
    milestone_metric: str
    progress_metric: str
    caption: str
    completed_steps: tuple[StepId, ...]
    stepper_line: str


def _nonempty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


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


def _project_initialized(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    phases = state.get("workspace_phases") or {}
    if isinstance(phases, dict) and phases.get("project_initialized") == "yes":
        return True
    return bool(state.get("run_id") or state.get("project_id"))


def completed_steps_from_state(state: dict[str, Any] | None) -> tuple[StepId, ...]:
    """Return completed lab steps in order (honest, gate-aware)."""
    done: list[StepId] = []
    if not _project_initialized(state):
        return tuple(done)
    done.append("project")
    if _has_problem_spec(state):
        done.append("problem")
    if _has_eda(state):
        done.append("eda")
    if _has_literature(state):
        done.append("literature")
    if read_h1_status(state) == "approved":
        done.append("h1")
    if has_experiment_results(state):
        done.append("modeling")
    if read_h2_status(state) == "approved":
        done.append("h2")
    if read_h3_status(state) == "approved":
        done.append("paper")
    if e2e_allowed(state):
        done.append("export")
    return tuple(done)


def current_step_from_state(state: dict[str, Any] | None) -> StepId:
    """Furthest active focus step (not merely completed).

    Later artifacts win when the user skipped an optional earlier panel
    (e.g. Research/H1 before attaching literature).
    """
    if not _project_initialized(state):
        return "project"

    h1 = read_h1_status(state)
    h2 = read_h2_status(state)
    h3 = read_h3_status(state)
    decided = {"pending", "revision_requested", "rejected"}

    if h3 == "approved":
        return "export"
    if h2 == "approved" or _has_paper_package(state) or h3 in decided:
        return "paper"
    if has_experiment_results(state) or h2 in decided:
        return "h2"
    if h1 == "approved":
        return "modeling"
    if _has_research_proposal(state) or h1 in decided:
        return "h1"
    if not _has_problem_spec(state):
        return "problem"
    if not _has_eda(state):
        return "eda"
    if not _has_literature(state):
        return "literature"
    return "h1"


def _sidebar_badge(step: StepId, state: dict[str, Any] | None) -> str:
    h1 = read_h1_status(state)
    h2 = read_h2_status(state)
    h3 = read_h3_status(state)
    if step == "project":
        return t("progress.badge.project")
    if step == "problem":
        return t("progress.badge.problem")
    if step == "eda":
        return t("progress.badge.eda")
    if step == "literature":
        return t("progress.badge.literature")
    if step == "h1":
        if h1 == "pending":
            return t("progress.badge.h1_pending")
        if h1 == "revision_requested":
            return t("progress.badge.h1_revision")
        if h1 == "rejected":
            return t("progress.badge.h1_rejected")
        if _has_research_proposal(state):
            return t("progress.badge.h1_ready")
        return t("progress.badge.h1_synth")
    if step == "modeling":
        if modeling_allowed(state):
            return t("progress.badge.modeling_ok")
        return t("progress.badge.modeling_blocked")
    if step == "h2":
        if h2 == "pending":
            return t("progress.badge.h2_pending")
        if h2 == "revision_requested":
            return t("progress.badge.h2_revision")
        return t("progress.badge.h2_run")
    if step == "paper":
        if h3 == "pending":
            return t("progress.badge.paper_pending")
        if h3 == "revision_requested":
            return t("progress.badge.paper_revision")
        if paper_allowed(state):
            return t("progress.badge.paper_ok")
        return t("progress.badge.paper_blocked")
    return t("progress.badge.export")


def _caption(step: StepId, state: dict[str, Any] | None) -> str:
    base = t("progress.caption.base")
    detail = t(f"progress.caption.{step}")
    strategy = None
    if state:
        phases = state.get("workspace_phases") or {}
        if isinstance(phases, dict):
            strategy = phases.get("strategy_modeling")
    strategy_note = ""
    if strategy and strategy != "NOT IMPLEMENTED":
        strategy_note = t("progress.strategy_phase", strategy=strategy)
    elif step in {"modeling", "h2", "paper", "export"}:
        strategy_note = t("progress.strategy_available")
    return f"{base} {detail}{strategy_note}"


def _stepper_line(current: StepId, completed: tuple[StepId, ...]) -> str:
    parts: list[str] = []
    for step in STEP_ORDER:
        label = step_label(step)
        if step in completed:
            parts.append(f"[x] {label}")
        elif step == current:
            parts.append(f"[>] {label}")
        else:
            parts.append(f"[ ] {label}")
    return " → ".join(parts)


def derive_progress_chrome(state: dict[str, Any] | None) -> ProgressChrome:
    """Build sidebar / metrics chrome from recorded ResearchState (or None)."""
    current = current_step_from_state(state)
    completed = completed_steps_from_state(state)
    label = step_label(current)
    total = len(STEP_ORDER)
    done_n = len(completed)
    return ProgressChrome(
        current_step=current,
        current_label=label,
        sidebar_badge=_sidebar_badge(current, state),
        milestone_metric=label,
        progress_metric=t("progress.metric_steps", done=done_n, total=total),
        caption=_caption(current, state),
        completed_steps=completed,
        stepper_line=_stepper_line(current, completed),
    )
