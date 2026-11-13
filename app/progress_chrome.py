"""Derive Streamlit progress chrome from ResearchState gates / workspace_phases.

Replaces hardcoded \"Phase 5\" / \"Workflow nodes 2\" / \"Phase 6 not started\" copy.
Does not start agents or change gate logic — presentation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

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
        return "Project · initialize inputs"
    if step == "problem":
        return "Problem · analyze statement"
    if step == "eda":
        return "EDA · chart plan & approve"
    if step == "literature":
        return "Literature · attach evidence"
    if step == "h1":
        if h1 == "pending":
            return "Research / H1 · awaiting approval"
        if h1 == "revision_requested":
            return "Research / H1 · revision requested"
        if h1 == "rejected":
            return "Research / H1 · rejected"
        if _has_research_proposal(state):
            return "Research / H1 · proposal ready"
        return "Research / H1 · synthesize candidates"
    if step == "modeling":
        if modeling_allowed(state):
            return "Modeling · available after H1"
        return "Modeling · blocked until H1"
    if step == "h2":
        if h2 == "pending":
            return "Validation / H2 · awaiting approval"
        if h2 == "revision_requested":
            return "Validation / H2 · revision requested"
        return "Validation / H2 · run sensitivity"
    if step == "paper":
        if h3 == "pending":
            return "Paper / H3 · awaiting approval"
        if h3 == "revision_requested":
            return "Paper / H3 · revision requested"
        if paper_allowed(state):
            return "Paper / H3 · available after H2"
        return "Paper / H3 · blocked until H2"
    return "Export · H3 approved"


def _caption(step: StepId, state: dict[str, Any] | None) -> str:
    base = (
        "Progress follows recorded gates: Project → Problem → EDA → Literature → "
        "Research/H1 → Modeling → Validation/H2 → Paper/H3 → Export. "
        "Human H1/H2/H3 never auto-approve."
    )
    if step == "project":
        detail = "Initialize a project to record inputs and dataset provenance."
    elif step == "problem":
        detail = "Run Problem Analyst for a validated ProblemSpecification."
    elif step == "eda":
        detail = "Approve a chart plan and persist independent EDA artifacts."
    elif step == "literature":
        detail = "Run Literature Evidence and attach cards to the recorded run."
    elif step == "h1":
        detail = "Synthesize research candidates, critique them, then approve H1 to unlock modeling."
    elif step == "modeling":
        detail = "H1 is approved — run Modeling & Experiment when ready (does not auto-start)."
    elif step == "h2":
        detail = "Experiment results are attached — run validation/sensitivity, then approve H2."
    elif step == "paper":
        detail = "H2 is approved — generate the paper package, then approve H3."
    else:
        detail = "H3 is approved — E2E / export may advance; research stays human-gated."
    strategy = None
    if state:
        phases = state.get("workspace_phases") or {}
        if isinstance(phases, dict):
            strategy = phases.get("strategy_modeling")
    strategy_note = ""
    if strategy and strategy != "NOT IMPLEMENTED":
        strategy_note = f" Strategy modeling phase: {strategy}."
    elif step in {"modeling", "h2", "paper", "export"}:
        strategy_note = " Strategy modeling is available via the Modeling panel after H1."
    return f"{base} {detail}{strategy_note}"


def _stepper_line(current: StepId, completed: tuple[StepId, ...]) -> str:
    parts: list[str] = []
    for step in STEP_ORDER:
        label = STEP_LABELS[step]
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
    label = STEP_LABELS[current]
    total = len(STEP_ORDER)
    done_n = len(completed)
    return ProgressChrome(
        current_step=current,
        current_label=label,
        sidebar_badge=_sidebar_badge(current, state),
        milestone_metric=label,
        progress_metric=f"{done_n}/{total} steps",
        caption=_caption(current, state),
        completed_steps=completed,
        stepper_line=_stepper_line(current, completed),
    )
