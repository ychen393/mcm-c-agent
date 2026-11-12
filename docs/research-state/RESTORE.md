# Research-state backup and restore

**Purpose:** Prevent loss of MCM runtime handoff docs that previously lived only on `docs/mcm-runtime-checkpoint`.

## Frozen originals (byte backup)

| Backup path | Source branch / SHA | Original path |
| --- | --- | --- |
| `docs/research-state/backup-2026-11-05/RUN_STATE.md` | `docs/mcm-runtime-checkpoint` @ `d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b` | `docs/RUN_STATE.md` |
| `docs/research-state/backup-2026-11-05/NEXT_ACTIONS.md` | same | `docs/NEXT_ACTIONS.md` |
| `docs/research-state/backup-2026-11-05/mcm_checkpoint.json` | same | `docs/state/mcm_checkpoint.json` |

Checkpoint ID in the backup: `mcm-c-2026-11-05-phase-b-live-planner`.

Google Docs human mirror (no secrets):  
https://docs.google.com/document/d/16zye72a1xP98hHKQpM6bm1GHvzInckVboni19n5_g_I/edit

## Working copies on the Phase 0 tip

The same three files are present at their canonical paths on `cursor/phase0-unified-baseline-ad8e`, with a Phase 0 addendum that records the new product tip. The **backup/** directory remains the immutable 2026-11-05 snapshot.

## Restore the 2026-11-05 snapshot exactly

```bash
git fetch origin
git switch cursor/phase0-unified-baseline-ad8e   # or any later tip that still carries the backup/
cp docs/research-state/backup-2026-11-05/RUN_STATE.md docs/RUN_STATE.md
cp docs/research-state/backup-2026-11-05/NEXT_ACTIONS.md docs/NEXT_ACTIONS.md
mkdir -p docs/state
cp docs/research-state/backup-2026-11-05/mcm_checkpoint.json docs/state/mcm_checkpoint.json
```

Or restore from the orphan branch without using the backup copies:

```bash
git fetch origin docs/mcm-runtime-checkpoint
git checkout d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b -- \
  docs/RUN_STATE.md docs/NEXT_ACTIONS.md docs/state/mcm_checkpoint.json
```

## Restore the Phase B code tip referenced by that checkpoint

The 2026-11-05 handoff pointed research execution at Visual EDA — **not** at Slice 3:

```bash
git fetch origin feature/m1b-visual-eda
git switch --detach 31bfdb322a86d8f3efe2ea1eb93e4af5794b6efc
python -m pip install -e ".[dev]"
pytest -q
streamlit run app/main.py --server.port 8502
```

## Restore / run the Phase 0 unified product baseline

```bash
git fetch origin cursor/phase0-unified-baseline-ad8e
git switch cursor/phase0-unified-baseline-ad8e
python -m pip install -e ".[dev]"
pytest -q
streamlit run app/main.py
# optional: docker compose up -d postgres
```

Never commit API keys, `.env`, private CSVs, or Streamlit session state.

## Integrity check

```bash
# Backup must match the checkpoint branch blobs
git fetch origin docs/mcm-runtime-checkpoint
diff -u <(git show d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b:docs/RUN_STATE.md) \
        docs/research-state/backup-2026-11-05/RUN_STATE.md
diff -u <(git show d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b:docs/NEXT_ACTIONS.md) \
        docs/research-state/backup-2026-11-05/NEXT_ACTIONS.md
diff -u <(git show d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b:docs/state/mcm_checkpoint.json) \
        docs/research-state/backup-2026-11-05/mcm_checkpoint.json
```

All three diffs must be empty.
