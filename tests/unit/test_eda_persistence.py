"""Phase 3 sanitized EDA persistence — compact summaries + artifact refs."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.lifecycle import LIFECYCLE_DATA_ANALYSIS_DONE
from core.project_store import LocalProjectStore
from schemas.persistence import FORBIDDEN_STATE_KEYS, assert_safe_for_persistence
from tools.chart_catalog import fallback_chart_plan
from tools.dataset_bundle import build_bundle_profiles, build_dataset_bundle
from tools.eda_artifacts import save_eda_artifacts
from tools.eda_engine import build_eda_report
from tools.eda_persistence import (
    build_compact_eda_report,
    compact_integration_confirmation,
    compact_profile_summary,
    compact_relationship_summary,
    persist_approved_eda_into_state,
)
from tools.relationship_profiler import preview_join, profile_relationships

GOLD = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1324.60\n"
    b"9/13/2016,1321.75\n"
    b"9/15/2016,1308.35\n"
)
BITCOIN = (
    b"Date,Value\n"
    b"9/12/2016,609.67\n"
    b"9/13/2016,610.92\n"
    b"9/15/2016,610.12\n"
)


def _bundle(project_id: str = "phase3-persist"):
    return build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)],
        project_id=project_id,
    )


def test_compact_profile_omits_forbidden_keys():
    bundle = _bundle()
    profiles = build_bundle_profiles(bundle)
    for profile in profiles.values():
        summary = compact_profile_summary(profile)
        assert_safe_for_persistence(summary, "profile")
        blob = str(summary)
        for key in FORBIDDEN_STATE_KEYS:
            assert key not in summary
            assert f"'{key}'" not in blob or key in {
                # sha256 / file names may coincidentally contain substrings; keys themselves must be absent
            }


def test_compact_relationship_and_confirmation_are_safe():
    bundle = _bundle()
    report = profile_relationships(bundle)
    rel = compact_relationship_summary(report)
    assert rel is not None
    assert rel["joined"] is False
    assert_safe_for_persistence(rel, "relationships")

    left = bundle.datasets[0]
    right = bundle.datasets[1]
    preview = preview_join(
        bundle,
        left_dataset_id=left.dataset_id,
        right_dataset_id=right.dataset_id,
        left_key="Date",
        right_key="Date",
        join_type="inner",
    )
    confirmation = compact_integration_confirmation(
        left_dataset_id=left.dataset_id,
        right_dataset_id=right.dataset_id,
        left_key="Date",
        right_key="Date",
        join_type="inner",
        preview=preview,
    )
    assert confirmation["joined"] is False
    assert confirmation["merged"] is False
    assert "preview_rows" not in confirmation
    assert_safe_for_persistence(confirmation, "confirmation")


def test_persist_approved_eda_registers_artifacts_and_lifecycle(tmp_path: Path):
    store = LocalProjectStore(tmp_path / "projects")
    bundle = _bundle("persist-eda")
    gold = bundle.datasets[0]
    loaded = bundle.loaded_dataset(gold.dataset_id)
    report = build_eda_report(loaded, bundle.project_id)
    artifacts = save_eda_artifacts(
        loaded,
        report,
        tmp_path / "outputs",
        chart_plan=fallback_chart_plan(report),
        human_approved=True,
    )
    profiles = build_bundle_profiles(bundle)
    compact = build_compact_eda_report(
        project_id=bundle.project_id,
        bundle_fingerprint=bundle.fingerprint,
        profiles=list(profiles.values()),
        relationship_summary=compact_relationship_summary(profile_relationships(bundle)),
        mode="single_file_charts",
    )
    assert_safe_for_persistence(compact, "eda_report")

    foundation = {
        "project_id": bundle.project_id,
        "project_name": "Persist EDA",
        "project_status": "initialized",
        "current_stage": "project_initialized",
        "analysis_status": "not_started",
        "lifecycle": "datasets_recorded",
        "problem_text": "2022 MCM C",
        "uploaded_files": [
            {
                "dataset_id": ref.dataset_id,
                "position": ref.position,
                "file_name": ref.file_name,
                "display_name": ref.display_name,
                "file_extension": ref.file_extension,
                "file_size_bytes": ref.file_size_bytes,
                "sha256": ref.sha256,
                "column_names": ref.column_names,
                "qualified_column_names": ref.qualified_column_names,
                "joined": False,
            }
            for ref in bundle.datasets
        ],
        "dataset_metadata": {"joined": False},
        "workspace_phases": {},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    project, run, saved = store.save_project_state(
        project_id=bundle.project_id,
        project_name="Persist EDA",
        state=foundation,
        input_signature="sig-phase3-eda",
    )
    assert run.run_id
    updated = persist_approved_eda_into_state(
        store,
        project_id=bundle.project_id,
        project_name="Persist EDA",
        state=saved,
        input_signature="sig-phase3-eda",
        compact_eda=compact,
        artifacts=artifacts,
        dataset_sha256=gold.sha256,
    )
    assert updated["lifecycle"] == LIFECYCLE_DATA_ANALYSIS_DONE
    assert updated["analysis_status"] == "data_analysis_done"
    assert updated["data_resume"] == "reupload_required"
    eda = updated["eda_report"]
    assert eda["joined"] is False
    assert eda["artifact_refs"]
    assert_safe_for_persistence(updated, "state")
    for key in ("sample_values", "numeric_summary", "preview_rows", "raw_bytes", "frame"):
        assert key not in str(eda.get("datasets"))
    listed = store.list_artifacts(bundle.project_id, run_id=updated["run_id"])
    assert listed
    assert project.project_id == bundle.project_id


def test_full_eda_report_dump_is_rejected_by_sanitize():
    bundle = _bundle()
    profile = next(iter(build_bundle_profiles(bundle).values()))
    with pytest.raises(ValueError, match="forbidden key"):
        assert_safe_for_persistence(profile.report.model_dump(mode="json"), "full_report")
