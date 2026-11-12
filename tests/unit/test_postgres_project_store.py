"""PostgresProjectStore against an in-process SQLite engine (no live Postgres required)."""

from __future__ import annotations

from sqlalchemy import create_engine

from core.foundation import build_initialized_state, foundation_input_signature, selection_token
from core.graph import build_foundation_graph
from core.project_store import PostgresProjectStore, make_approval
from tools.dataset_bundle import build_dataset_bundle

GOLD = b"Date,USD (PM)\n9/12/2016,1324.60\n9/13/2016,1321.75\n"
BITCOIN = b"Date,Value\n9/11/2016,621.65\n9/12/2016,609.67\n"


def _bundle_state(uploads, *, project_id="pg-demo", revision=0):
    bundle = build_dataset_bundle(uploads, project_id=project_id)
    state = build_initialized_state(
        project_id=project_id,
        project_name="PG Demo",
        problem_text="problem",
        bundle=bundle,
        selection_status="ready",
        llm_config_revision=revision,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result = build_foundation_graph().invoke(state)
    token = selection_token(uploads, fingerprint=bundle.fingerprint, rejected=False)
    signature = foundation_input_signature(
        project_id=project_id,
        project_name="PG Demo",
        problem_text="problem",
        selection_token_value=token,
        llm_config_revision=revision,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    return result, signature


def test_sqlite_backed_postgres_store_save_reopen_invalidate(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1.db'}")
    store = PostgresProjectStore(engine)
    assert store.info().backend == "postgres"

    uploads = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]
    state, signature = _bundle_state(uploads)
    project, run, saved = store.save_project_state(
        project_id="pg-demo",
        project_name="PG Demo",
        state=state,
        input_signature=signature,
    )
    assert len(saved["uploaded_files"]) == 2
    assert project.active_run_id == run.run_id

    store.add_approval(
        make_approval(
            project_id="pg-demo",
            run_id=run.run_id,
            gate="H1",
            status="approved",
            notes="should invalidate",
        )
    )

    restored = store.load_active_state("pg-demo")
    assert restored is not None
    assert restored["run_id"] == run.run_id

    # New revision → stale previous + invalidated approval
    state2, signature2 = _bundle_state(uploads, revision=2)
    _p, run2, _ = store.save_project_state(
        project_id="pg-demo",
        project_name="PG Demo",
        state=state2,
        input_signature=signature2,
    )
    assert run2.version == 2
    history = store.history("pg-demo")
    assert {entry.run_id: entry.status for entry in history}[run.run_id] == "stale"
    assert store.invalidate_approvals("pg-demo", run2.run_id, reason="noop") == 0
