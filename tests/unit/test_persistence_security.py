"""P0 security regressions for Phase 1 persistence."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from core.foundation import build_initialized_state, foundation_input_signature, selection_token
from core.graph import build_foundation_graph
from core.ids import new_run_id
from core.project_store import (
    LocalProjectStore,
    PostgresProjectStore,
    make_artifact,
    open_project_store,
    read_last_backend,
)
from schemas.persistence import (
    REUPLOAD_REQUIRED_MESSAGE,
    ArtifactRefRecord,
    assert_safe_for_persistence,
    sanitize_state_for_persistence,
)
from tools.dataset_bundle import build_dataset_bundle

GOLD = b"Date,USD (PM)\n9/12/2016,1324.60\n9/13/2016,1321.75\n"
SECRET = "sk-sensitive-nested"


def _clean_state(uploads=None, *, project_id="sec-demo"):
    uploads = uploads or [("LBMA-GOLD.csv", GOLD)]
    bundle = build_dataset_bundle(uploads, project_id=project_id)
    state = build_initialized_state(
        project_id=project_id,
        project_name="Security Demo",
        problem_text="problem",
        bundle=bundle,
        selection_status="ready",
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result = build_foundation_graph().invoke(state)
    token = selection_token(uploads, fingerprint=bundle.fingerprint, rejected=False)
    signature = foundation_input_signature(
        project_id=project_id,
        project_name="Security Demo",
        problem_text="problem",
        selection_token_value=token,
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    return result, signature


def test_nested_secrets_in_metadata_and_uploads_fail_closed():
    state, _ = _clean_state()
    dirty = dict(state)
    dirty["dataset_metadata"] = dict(dirty["dataset_metadata"])
    dirty["dataset_metadata"]["deepseek_api_key"] = SECRET
    with pytest.raises(ValueError, match="forbidden key"):
        sanitize_state_for_persistence(dirty)

    dirty2 = dict(state)
    files = [dict(item) for item in dirty2["uploaded_files"]]
    files[0]["api_key"] = SECRET
    dirty2["uploaded_files"] = files
    with pytest.raises(ValueError, match="forbidden key"):
        sanitize_state_for_persistence(dirty2)


def test_arbitrary_extra_nested_secret_and_bytes_fail_closed():
    state, _ = _clean_state()
    dirty = dict(state)
    dirty["extra_blob"] = {"wrapper": {"openai_api_key": SECRET}}
    with pytest.raises(ValueError, match="forbidden key"):
        assert_safe_for_persistence(dirty)
    dirty_bytes = dict(state)
    dirty_bytes["payload"] = {"raw_bytes": b"not-allowed"}
    with pytest.raises(ValueError, match="forbidden key|raw bytes"):
        sanitize_state_for_persistence(dirty_bytes)


def test_local_and_sqlite_stores_refuse_nested_secrets(tmp_path):
    state, signature = _clean_state(project_id="sec-local")
    dirty = dict(state)
    dirty["dataset_metadata"] = dict(dirty["dataset_metadata"])
    dirty["dataset_metadata"]["nested"] = {"llm_api_key": SECRET}

    local = LocalProjectStore(tmp_path / "projects")
    with pytest.raises(ValueError, match="forbidden key"):
        local.save_project_state(
            project_id="sec-local",
            project_name="Security Demo",
            state=dirty,
            input_signature=signature,
        )
    assert not (tmp_path / "projects" / "sec-local").exists()

    engine = create_engine(f"sqlite:///{tmp_path / 'sec.db'}")
    pg = PostgresProjectStore(engine)
    with pytest.raises(ValueError, match="forbidden key"):
        pg.save_project_state(
            project_id="sec-local",
            project_name="Security Demo",
            state=dirty,
            input_signature=signature,
        )
    assert pg.get_project("sec-local") is None


def test_artifact_metadata_rejects_nested_secrets():
    with pytest.raises(ValueError, match="forbidden key"):
        ArtifactRefRecord(
            artifact_id="art_0123456789ab",
            project_id="sec-demo",
            run_id=new_run_id(),
            kind="eda_report",
            uri="outputs/x.json",
            created_at="2026-11-12T00:00:00Z",
            metadata={"provider": {"deepseek_api_key": SECRET}},
        )


def test_run_id_traversal_and_unknown_read_do_not_mutate_fs(tmp_path):
    root = tmp_path / "projects"
    store = LocalProjectStore(root)
    state, signature = _clean_state(project_id="sec-path")
    project, run, _ = store.save_project_state(
        project_id="sec-path",
        project_name="Security Demo",
        state=state,
        input_signature=signature,
    )
    before = {p.relative_to(root) for p in root.rglob("*")}

    assert store.load_run_state("sec-path", "../etc/passwd") is None
    assert store.load_run_state("sec-path", "/tmp/evil") is None
    assert store.continue_run("sec-path", "..") is None
    assert store.list_artifacts("sec-path", run_id="../x") == []
    assert store.invalidate_approvals("sec-path", "../x", reason="test") == 0
    unknown = "run_deadbeefcafe"
    assert store.load_run_state("sec-path", unknown) is None

    after = {p.relative_to(root) for p in root.rglob("*")}
    assert after == before
    assert not (root / "etc").exists()
    assert not (root / "sec-path" / "runs" / unknown).exists()
    # Valid run still readable.
    assert store.load_run_state("sec-path", run.run_id) is not None
    assert project.active_run_id == run.run_id


def test_reopen_is_provenance_only_reupload_required(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    state, signature = _clean_state()
    store.save_project_state(
        project_id="sec-demo",
        project_name="Security Demo",
        state=state,
        input_signature=signature,
    )
    loaded = store.load_active_state("sec-demo")
    assert loaded is not None
    assert loaded["data_resume"] == "reupload_required"
    assert any(err.get("code") == "reupload_required" for err in loaded["errors"])
    assert "DataFrames" in REUPLOAD_REQUIRED_MESSAGE or "re-upload" in REUPLOAD_REQUIRED_MESSAGE.lower()
    # No frame/bytes restored
    dump = str(loaded)
    assert "1324.60" not in dump
    assert "raw_bytes" not in dump


def test_backend_auto_mismatch_warns_and_does_not_lose_local_projects(tmp_path):
    root = tmp_path / "projects"
    local = open_project_store(
        database_url="postgresql+psycopg://nobody:bad@127.0.0.1:1/missing",
        projects_root=root,
        prefer_postgres=True,
        force_backend="local",
    )
    assert local.info().backend == "local"
    assert read_last_backend(root) == "local"
    state, signature = _clean_state(project_id="keep-me")
    local.save_project_state(
        project_id="keep-me",
        project_name="Security Demo",
        state=state,
        input_signature=signature,
    )
    assert local.list_projects()

    # Simulate a later process that lands on a different backend marker target.
    # Force postgres against unreachable DB → falls back to local without loss.
    again = open_project_store(
        database_url="postgresql+psycopg://nobody:bad@127.0.0.1:1/missing",
        projects_root=root,
        prefer_postgres=True,
        force_backend=None,
    )
    assert again.info().backend == "local"
    assert again.get_project("keep-me") is not None

    # Marker says local; opening an explicit postgres store (sqlite stand-in) records mismatch.
    engine = create_engine(f"sqlite:///{tmp_path / 'other.db'}")
    from core.project_store import write_last_backend, backend_mismatch_message

    write_last_backend(root, "local")
    message = backend_mismatch_message("local", "postgres", local_root=root.resolve())
    assert message is not None
    assert "not lost" in message.lower() or "not auto-imported" in message.lower()
    pg = PostgresProjectStore(
        engine,
        backend_changed=True,
        previous_backend="local",
        mismatch_message=message,
        local_root_hint=root,
    )
    info = pg.info()
    assert info.backend_changed is True
    assert info.backend_mismatch_message
    # Local projects remain on disk even though postgres store is empty.
    assert LocalProjectStore(root).get_project("keep-me") is not None
    assert pg.list_projects() == []


def test_make_artifact_rejects_nested_secret_metadata():
    with pytest.raises(ValueError, match="forbidden key"):
        make_artifact(
            project_id="sec-demo",
            run_id=new_run_id(),
            kind="note",
            uri="outputs/x.txt",
            sha256=hashlib.sha256(b"x").hexdigest(),
            metadata={"auth": {"token": SECRET}},
        )


def test_unknown_upload_extra_fields_are_dropped_not_stored(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    state, signature = _clean_state()
    files = [dict(item) for item in state["uploaded_files"]]
    files[0]["harmless_extra"] = "drop-me"
    state = dict(state)
    state["uploaded_files"] = files
    _p, _r, saved = store.save_project_state(
        project_id="sec-demo",
        project_name="Security Demo",
        state=state,
        input_signature=signature,
    )
    assert "harmless_extra" not in saved["uploaded_files"][0]
    disk = Path(tmp_path / "projects" / "sec-demo" / "runs" / saved["run_id"] / "state.json")
    text = disk.read_text(encoding="utf-8")
    assert "harmless_extra" not in text
    assert SECRET not in text


def test_foundation_rejects_authorization_and_token_like_persistence():
    """P1-1: in-memory ResearchState uses the same heuristics as persistence."""
    from core.foundation import (
        build_initialized_state,
        sanitize_uploaded_files,
        _reject_unsafe_values,
    )
    from core.graph import build_foundation_graph
    from schemas.persistence import assert_safe_for_persistence

    state, _ = _clean_state()
    poisoned = [dict(item) for item in state["uploaded_files"]]
    poisoned[0]["authorization"] = "Bearer secret"
    with pytest.raises(ValueError, match="forbidden key"):
        assert_safe_for_persistence({"uploaded_files": poisoned})
    with pytest.raises(ValueError, match="forbidden key"):
        sanitize_uploaded_files(poisoned)

    nested = dict(state)
    nested["dataset_metadata"] = dict(nested["dataset_metadata"])
    nested["dataset_metadata"]["provider_token"] = SECRET
    with pytest.raises(TypeError, match="cannot contain|forbidden"):
        _reject_unsafe_values(nested)

    # Clean build + graph output never carries authorization / token keys.
    clean = build_initialized_state(
        project_id="sec-demo",
        project_name="Security Demo",
        problem_text="problem",
        bundle=build_dataset_bundle([("LBMA-GOLD.csv", GOLD)], project_id="sec-demo"),
        selection_status="ready",
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result = build_foundation_graph().invoke(clean)
    dump = str(result)
    assert "authorization" not in dump.lower()
    assert "Bearer" not in dump
    assert SECRET not in dump
    for item in result["uploaded_files"]:
        assert "authorization" not in item
        assert "token" not in item
        assert "api_key" not in item


def test_poisoned_stored_state_soft_fails_on_load_and_continue(tmp_path):
    """P1-2: tampered state.json must not raise 'Refusing to persist' on read."""
    store = LocalProjectStore(tmp_path / "projects")
    state, signature = _clean_state(project_id="poison")
    _p, run, saved = store.save_project_state(
        project_id="poison",
        project_name="Security Demo",
        state=state,
        input_signature=signature,
    )
    path = tmp_path / "projects" / "poison" / "runs" / run.run_id / "state.json"
    planted = dict(saved)
    planted["dataset_metadata"] = dict(planted.get("dataset_metadata") or {})
    planted["dataset_metadata"]["api_key"] = SECRET
    path.write_text(__import__("json").dumps(planted), encoding="utf-8")

    assert store.load_run_state("poison", run.run_id) is None
    assert store.continue_run("poison", run.run_id) is None
    assert store.load_active_state("poison") is None

    engine = create_engine(f"sqlite:///{tmp_path / 'poison.db'}")
    pg = PostgresProjectStore(engine)
    _p2, run2, saved2 = pg.save_project_state(
        project_id="poison-pg",
        project_name="Security Demo",
        state=state,
        input_signature=signature,
    )
    # Plant nested secret directly into ORM JSON.
    from database.models import ResearchRunRow
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        row = session.get(ResearchRunRow, run2.run_id)
        assert row is not None
        poisoned_json = dict(row.state_json or {})
        poisoned_json["dataset_metadata"] = dict(poisoned_json.get("dataset_metadata") or {})
        poisoned_json["dataset_metadata"]["api_key"] = SECRET
        row.state_json = poisoned_json
        session.commit()

    assert pg.load_run_state("poison-pg", run2.run_id) is None
    assert pg.continue_run("poison-pg", run2.run_id) is None
    assert pg.load_active_state("poison-pg") is None
