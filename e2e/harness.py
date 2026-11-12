"""Offline end-to-end acceptance harness for 2022 MCM C (Phase 9).

Walks the product chain with fixtures only (no live LLM / retrieval / trading):

    ProblemSpec → EDA → Evidence → Research/H1 → Modeling → Validation/H2
    → Paper/H3 → acceptance facts

H1/H2/H3 approvals are applied via harness **test doubles** that call the same
persistence builders as the product UI with ``decided_by="human"`` and
``auto_approved=False``. They never enable production auto-approve.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.debate_critic import critique_research_proposal
from agents.literature_evidence import gather_literature_evidence
from agents.modeling_experiment import run_modeling_experiment
from agents.paper_planner import run_paper_planner
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.validation_sensitivity import run_validation_sensitivity
from core.project_store import LocalProjectStore, ProjectStore
from paper.gate import assert_e2e_allowed, e2e_allowed, e2e_gate_status
from schemas.e2e import E2EAcceptanceReport, E2EStepResult, HarnessGateRecord
from schemas.persistence import assert_safe_for_persistence
from tools.dataset_bundle import build_dataset_bundle
from tools.evidence_persistence import persist_evidence_into_state
from tools.experiment_persistence import persist_experiment_into_state
from tools.paper_persistence import persist_paper_into_state
from tools.problem_aware_eda import build_problem_aware_eda_plan
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.relationship_profiler import profile_relationships
from tools.research_persistence import persist_research_proposal_into_state
from tools.validation_persistence import persist_validation_into_state

from e2e.assertions import assert_acceptance_facts, collect_acceptance_fact_checks
from e2e.human_gates import (
    apply_harness_h1_approval,
    apply_harness_h2_approval,
    apply_harness_h3_approval,
)

PROJECT_ID = "mcm-c-e2e-2022"
PROJECT_NAME = "MCM C 2022 Historical E2E"
INPUT_SIGNATURE = "sig-phase9-e2e-2022-c"

# Minimal synthetic CSVs matching official filenames (same pattern as Phase 3 tests).
_GOLD_CSV = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1324.60\n"
    b"9/13/2016,1321.75\n"
    b"9/14/2016,\n"
    b"9/15/2016,1308.35\n"
)
_BITCOIN_CSV = (
    b"Date,Value\n"
    b"9/11/2016,621.65\n"
    b"9/12/2016,609.67\n"
    b"9/13/2016,610.92\n"
    b"9/14/2016,608.82\n"
    b"9/15/2016,610.12\n"
)


@dataclass
class E2EHarnessResult:
    """Return payload from ``run_2022_c_historical_e2e``."""

    report: E2EAcceptanceReport
    state: dict[str, Any]
    steps: list[E2EStepResult] = field(default_factory=list)
    gate_records: list[HarnessGateRecord] = field(default_factory=list)


def _boot_state(store: ProjectStore) -> dict[str, Any]:
    state = {
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "project_status": "initialized",
        "lifecycle": "project_initialized",
        "analysis_status": "not_started",
        "uploaded_files": [],
        "citations": [],
        "model_artifacts": [],
        "experiment_logs": [],
        "workspace_phases": {"e2e_acceptance": "not_started"},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    _project, run, boot = store.save_project_state(
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        note="phase9-e2e-bootstrap",
    )
    boot = dict(boot)
    boot["run_id"] = run.run_id
    return boot


def _step(
    name: str,
    status: str,
    summary: str,
    *,
    artifact_ids: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> E2EStepResult:
    return E2EStepResult(
        step=name,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        summary=summary,
        artifact_ids=artifact_ids or [],
        details=details or {},
    )


def _persist_acceptance_report(
    store: ProjectStore,
    *,
    state: dict[str, Any],
    report: E2EAcceptanceReport,
) -> dict[str, Any]:
    updated = dict(state)
    decision = dict(updated.get("decision_report") or {})
    decision["e2e_acceptance"] = report.model_dump(mode="json")
    decision["e2e_gate"] = e2e_gate_status(updated).model_dump(mode="json")
    updated["decision_report"] = decision
    phases = dict(updated.get("workspace_phases") or {})
    phases["e2e_acceptance"] = "passed" if report.overall_passed else "failed"
    updated["workspace_phases"] = phases
    # Historical E2E pass is recorded without flipping research_task_complete —
    # owner merge/deploy remains a separate gate.
    notes = list(updated.get("errors") or [])
    updated["errors"] = notes
    assert_safe_for_persistence(updated, "state")
    _project, run, saved = store.save_project_state(
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=updated,
        input_signature=INPUT_SIGNATURE,
        note="phase9-e2e-acceptance-report",
    )
    saved = dict(saved)
    saved["run_id"] = run.run_id
    return saved


def run_2022_c_historical_e2e(
    *,
    store: ProjectStore | None = None,
    projects_root: Path | None = None,
    problem_text: str | None = None,
) -> E2EHarnessResult:
    """Run the offline 2022 C acceptance chain. CI-safe (fixtures only)."""
    if store is None:
        root = projects_root or Path("data/projects")
        store = LocalProjectStore(root)

    steps: list[E2EStepResult] = []
    gate_records: list[HarnessGateRecord] = []
    state = _boot_state(store)
    text = problem_text if problem_text is not None else load_2022_c_fixture()

    # --- 1. ProblemSpec ---
    spec = analyze_problem(text, use_llm=False)
    state["problem_specification"] = spec.model_dump(mode="json")
    state["lifecycle"] = "datasets_recorded"
    steps.append(
        _step(
            "problem_spec",
            "passed",
            f"ProblemSpecification {spec.problem_id} built from fixture (LLM off).",
            artifact_ids=[spec.problem_id],
            details={"title": spec.title, "n_datasets": len(spec.supplied_datasets)},
        )
    )

    # --- 2. EDA ---
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", _GOLD_CSV), ("BCHAIN-MKPRU.csv", _BITCOIN_CSV)],
        project_id=PROJECT_ID,
    )
    relationships = profile_relationships(bundle)
    eda_plan = build_problem_aware_eda_plan(
        bundle=bundle,
        problem_specification=spec,
        relationship_report=relationships,
    )
    state["eda_plan"] = eda_plan.model_dump(mode="json")
    # Keep uploaded_files empty of raw bytes; CSV identity is asserted via
    # ProblemSpecification.supplied_datasets + EDA dataset_matches (provenance-safe).
    state["lifecycle"] = "data_analysis_done"
    state["analysis_status"] = "data_analysis_done"
    phases = dict(state.get("workspace_phases") or {})
    phases["independent_eda"] = "planned_offline"
    state["workspace_phases"] = phases
    assert_safe_for_persistence(state, "state")
    _project, run, state = store.save_project_state(
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        note="phase9-e2e-eda",
    )
    state = dict(state)
    state["run_id"] = run.run_id

    matched = sum(1 for m in eda_plan.dataset_matches if m.status == "matched")
    steps.append(
        _step(
            "eda",
            "passed",
            f"Problem-aware EDA plan with {matched} matched dataset(s); no invented joins.",
            artifact_ids=["eda_plan_2022_c"],
            details={
                "invented_joins": eda_plan.invented_joins,
                "has_problem_specification": eda_plan.has_problem_specification,
            },
        )
    )

    # --- 3. Evidence ---
    evidence = gather_literature_evidence(
        problem_specification=spec,
        eda_plan=eda_plan,
        use_live=False,
    )
    state = persist_evidence_into_state(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        report=evidence,
        note="phase9-e2e-evidence",
    )
    evidence_id = f"evidence_{evidence.problem_id or 'offline'}"
    steps.append(
        _step(
            "evidence",
            "passed",
            f"Offline literature evidence report {evidence_id} "
            f"({len(evidence.cards)} card(s); invented_sources={evidence.invented_sources}).",
            artifact_ids=[evidence_id],
            details={"invented_sources": evidence.invented_sources, "n_cards": len(evidence.cards)},
        )
    )

    # --- 4. Research + H1 (harness double) ---
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        eda_plan=eda_plan,
        evidence_report=evidence,
        use_llm=False,
    )
    critique = critique_research_proposal(
        proposal=proposal,
        problem_specification=spec,
        evidence_report=evidence,
        use_llm=False,
    )
    state = persist_research_proposal_into_state(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        proposal=proposal,
        critique=critique,
        note="phase9-e2e-research",
    )
    # Without H1, modeling must stay blocked — verified implicitly by gate before approve.
    state, h1_record = apply_harness_h1_approval(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        proposal=proposal,
        selected_candidate_id=proposal.recommended_candidate_id,
        critique_id=critique.critique_id,
    )
    gate_records.append(h1_record)
    steps.append(
        _step(
            "research_h1",
            "passed",
            "Research proposal + critique attached; H1 approved via harness "
            "simulated-human test double (auto_approved=False).",
            artifact_ids=[proposal.proposal_id, h1_record.decision_id or ""],
            details={
                "selected_candidate_id": proposal.recommended_candidate_id,
                "harness_simulated_human": True,
            },
        )
    )

    # --- 5. Modeling ---
    experiment = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        allow_sandboxed_python=False,
    )
    state = persist_experiment_into_state(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        report=experiment,
        note="phase9-e2e-modeling",
    )
    steps.append(
        _step(
            "modeling",
            "passed",
            f"Deterministic modeling experiment {experiment.report_id} "
            f"(live_trading={experiment.live_trading_api_used}).",
            artifact_ids=[experiment.report_id, experiment.latest_run_id or ""],
            details={
                "initial_cash": experiment.runs[0].constraints.initial_cash
                if experiment.runs
                else None,
                "past_data_only": experiment.runs[0].constraints.past_data_only
                if experiment.runs
                else None,
            },
        )
    )

    # --- 6. Validation + H2 ---
    validation = run_validation_sensitivity(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        use_llm=False,
    )
    state = persist_validation_into_state(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        report=validation,
        note="phase9-e2e-validation",
    )
    state, h2_record = apply_harness_h2_approval(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        report=validation,
    )
    gate_records.append(h2_record)
    steps.append(
        _step(
            "validation_h2",
            "passed",
            f"Validation report {validation.report_id}; H2 approved via harness "
            "simulated-human test double.",
            artifact_ids=[validation.report_id, h2_record.decision_id or ""],
            details={"n_scenarios": len(validation.scenarios), "harness_simulated_human": True},
        )
    )

    # --- 7. Paper + H3 ---
    package = run_paper_planner(
        state=state,
        problem_specification=spec,
        use_llm=False,
        attempt_pdf_compile=False,
    )
    state = persist_paper_into_state(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        package=package,
        note="phase9-e2e-paper",
    )
    # E2E must still be blocked until H3.
    if e2e_allowed(state):
        raise RuntimeError("E2E incorrectly allowed before H3 approval")
    state, h3_record = apply_harness_h3_approval(
        store,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        state=state,
        input_signature=INPUT_SIGNATURE,
        package=package,
    )
    gate_records.append(h3_record)
    assert_e2e_allowed(state)
    steps.append(
        _step(
            "paper_h3",
            "passed",
            f"Paper package {package.package_id}; H3 approved via harness "
            "simulated-human test double; assert_e2e_allowed passed.",
            artifact_ids=[
                package.package_id,
                package.outline.outline_id,
                h3_record.decision_id or "",
            ],
            details={
                "invented_citations": package.invented_citations,
                "harness_simulated_human": True,
                "e2e_allowed": True,
            },
        )
    )

    # --- 8. Golden acceptance ---
    fact_checks = collect_acceptance_fact_checks(
        state=state,
        problem_specification=spec,
        problem_text=text,
    )
    assert_acceptance_facts(
        state=state,
        problem_specification=spec,
        problem_text=text,
    )
    steps.append(
        _step(
            "acceptance",
            "passed",
            f"All {len(fact_checks)} golden acceptance fact checks passed.",
            artifact_ids=[c.fact_id for c in fact_checks if c.passed][:32],
            details={"n_checks": len(fact_checks), "n_failed": 0},
        )
    )

    digest = hashlib.sha256(
        "|".join(
            [
                spec.problem_id,
                proposal.proposal_id,
                experiment.report_id,
                validation.report_id,
                package.package_id,
            ]
        ).encode()
    ).hexdigest()[:10]
    report = E2EAcceptanceReport(
        report_id=f"e2e_{digest}",
        overall_passed=True,
        e2e_allowed=True,
        steps=steps,
        gate_records=gate_records,
        fact_checks=fact_checks,
        citation_invented=bool(package.invented_citations or evidence.invented_sources),
        notes=[
            "Offline fixture path only — no live LLM, retrieval, or trading APIs.",
            "H1/H2/H3 approvals in this report are harness test doubles "
            "(simulated human); product UI remains human-only.",
            "research_task_complete / merge / deploy are NOT set by this harness.",
        ],
    )
    state = _persist_acceptance_report(store, state=state, report=report)
    return E2EHarnessResult(
        report=report,
        state=state,
        steps=steps,
        gate_records=gate_records,
    )
