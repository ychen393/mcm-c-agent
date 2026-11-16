"""Persist compact, source-hashed EDA interpretations for later model advice."""
from core.project_store import LocalProjectStore
from app.eda_interpretation import bundle_insights
from tools.dataset_bundle import build_bundle_profiles, build_dataset_bundle
from tools.eda_persistence import build_compact_eda_report, persist_approved_eda_into_state

GOLD = b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1700\n2022-01-11,1600\n"
BTC = b"Date,Value\n2022-01-07,40000\n2022-01-08,43000\n2022-01-09,41000\n"


def test_source_evidence_survives_project_state_roundtrip(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    initial = {
        "project_id": "mcm-eda-study",
        "project_name": "EDA-to-strategy",
        "project_status": "initialized",
        "lifecycle": "project_initialized",
        "analysis_status": "not_started",
        "uploaded_files": [],
        "citations": [],
        "model_artifacts": [],
        "experiment_logs": [],
        "workspace_phases": {},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    _p, run, state = store.save_project_state(
        project_id="mcm-eda-study",
        project_name="EDA-to-strategy",
        state=initial,
        input_signature="eda-test-sig",
        note="init",
    )
    state = dict(state)
    state["run_id"] = run.run_id
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BTC)],
        project_id="mcm-eda-study",
    )
    profiles = build_bundle_profiles(bundle)
    compact = build_compact_eda_report(
        project_id=bundle.project_id,
        bundle_fingerprint=bundle.fingerprint,
        profiles=list(profiles.values()),
        mode="independent_multi",
    )
    compact["interpreted_findings"] = bundle_insights(bundle)
    saved = persist_approved_eda_into_state(
        store,
        project_id="mcm-eda-study",
        project_name="EDA-to-strategy",
        state=state,
        input_signature="eda-test-sig",
        compact_eda=compact,
    )
    evidence = saved["eda_report"]["interpreted_findings"]
    assert evidence["bundle_fingerprint"] == bundle.fingerprint
    assert len(evidence["datasets"]) == 2
    assert evidence["datasets"][0]["valid_prices"] == 3
    assert evidence["datasets"][0]["sha256"] == bundle.datasets[0].sha256
    assert saved["workspace_phases"]["independent_eda"] == "done"
    assert not evidence["jointly_modeled"]
