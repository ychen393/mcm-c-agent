"""Phase 4 evidence persistence + sanitize checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.literature_evidence import gather_literature_evidence
from agents.problem_analyst import analyze_problem
from core.project_store import LocalProjectStore
from schemas.persistence import sanitize_state_for_persistence
from tools.evidence_persistence import (
    citation_entries_from_report,
    compact_evidence_report,
    persist_evidence_into_state,
)
from tools.problem_spec_2022_c import load_2022_c_fixture


@pytest.fixture
def report():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    return gather_literature_evidence(problem_specification=spec, use_live=False)


def test_compact_evidence_report_is_persistence_safe(report):
    compact = compact_evidence_report(report)
    assert compact["invented_sources"] is False
    assert compact["report_version"]
    sanitize_state_for_persistence(
        {
            "project_id": "mcm-c-demo",
            "project_name": "MCM C Demo Project",
            "project_status": "initialized",
            "lifecycle": "project_initialized",
            "uploaded_files": [],
            "evidence_report": compact,
            "citations": citation_entries_from_report(report),
        }
    )


def test_persist_evidence_into_state(tmp_path: Path, report):
    store = LocalProjectStore(root=tmp_path / "projects")
    state = {
        "project_id": "mcm-c-demo",
        "project_name": "MCM C Demo Project",
        "project_status": "initialized",
        "lifecycle": "data_analysis_done",
        "analysis_status": "data_analysis_done",
        "uploaded_files": [],
        "citations": [],
        "workspace_phases": {},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    _project, run, boot = store.save_project_state(
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase4-test",
        note="bootstrap",
    )
    boot = dict(boot)
    boot["run_id"] = run.run_id
    saved = persist_evidence_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=boot,
        input_signature="sig-phase4-test",
        report=report,
    )
    assert saved.get("evidence_report")
    assert saved.get("citations")
    assert saved["workspace_phases"]["literature_evidence"] == "recorded"
    assert saved.get("invented_sources") is not True
    # Research task must remain incomplete.
    assert saved.get("lifecycle") != "research_task_complete"


def test_refuse_invented_report_payload():
    with pytest.raises(Exception):
        compact_evidence_report({"invented_sources": True, "cards": []})
