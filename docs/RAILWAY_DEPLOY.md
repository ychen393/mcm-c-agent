# Railway deploy guide (packaging only)

**Status:** Config / docs for a future Railway deploy. This repository change does **not** create a Railway project, PostgreSQL plugin, Volume, or public URL. Owner (yihan chen) must approve before any billable Railway spend.

**Related:** Project audit `docs/deployment-readiness-audit.md` (Cursor store); container files `Dockerfile`, `railway.toml`, `.dockerignore`.

---

## What this packages

| Piece | Purpose |
|---|---|
| `Dockerfile` | Python 3.11 image; Streamlit on `$PORT`; LLM flags default off; paths under `/data` |
| `railway.toml` | Dockerfile builder, start command, `/_stcore/health` healthcheck |
| `APP_PASSWORD` | Server-side shared password gate (`app/auth.py`) — blocks Research Lab + API Settings until unlocked |
| `PROJECT_STORE_BACKEND=postgres` | Avoid silent local-disk fallback in production-like envs |
| `UPLOAD_DIR` / `OUTPUT_DIR` / `PROJECTS_DIR` | Configurable dirs for a Railway Volume mount |

---

## Start command

Railway injects `PORT`. Equivalent commands:

```bash
streamlit run app/main.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
```

Healthcheck path: `/_stcore/health`.

---

## Environment variables (Secrets)

Set these as Railway **Variables / Secrets**. Never bake secrets into the image or git.

| Variable | Required | Demo value / notes |
|---|---|---|
| `APP_ENV` | yes | `production` or `railway` (fail-closed auth) |
| `APP_PASSWORD` | **yes** in production-like | Strong shared password; rotate away from any local default |
| `DATABASE_URL` | yes | Railway Postgres URL; use `postgresql+psycopg://…` for SQLAlchemy |
| `PROJECT_STORE_BACKEND` | yes | `postgres` |
| `UPLOAD_DIR` | yes | `/data/uploads` |
| `OUTPUT_DIR` | yes | `/data/outputs` |
| `PROJECTS_DIR` | recommended | `/data/projects` |
| `PROBLEM_ANALYST_USE_LLM` | yes | `false` |
| `LITERATURE_LIVE_RETRIEVAL` | yes | `false` |
| `RESEARCH_STRATEGY_USE_LLM` | yes | `false` |
| `VALIDATION_USE_LLM` | yes | `false` |
| `PAPER_USE_LLM` | yes | `false` |
| `PORT` | injected | Do not hardcode |
| LLM API keys | **omit** for paid-free demo | Keep unset until owner unlocks LLM |

`CHECKPOINT_DATABASE_URL` is optional for this demo path.

**Do not** ship `mcm_dev_password` in production `DATABASE_URL`.

---

## Volume mounts

Charts, PDF soft-fail artifacts, uploads, and the local project-store tree are filesystem paths. On ephemeral disks they vanish on restart.

Recommended single Volume mounted at `/data`:

| Host mount | Env |
|---|---|
| `/data/uploads` | `UPLOAD_DIR` |
| `/data/outputs` | `OUTPUT_DIR` |
| `/data/projects` | `PROJECTS_DIR` |

**CSV bytes are not stored in Postgres.** Reopen always requires re-upload of matching files (SHA-256). Volume persistence covers charts/reports/paths referenced by `artifact_refs.uri`, not raw CSV recovery.

PDF compile needs TeX tooling; the default image **omits** TeX (soft-fail). Add TeX only if live PDF is required.

---

## Postgres

1. Owner approves → create Railway PostgreSQL (billable).
2. Copy the connection URL into `DATABASE_URL` (SQLAlchemy form: `postgresql+psycopg://…`).
3. Set `PROJECT_STORE_BACKEND=postgres`.
4. Schema is created via SQLAlchemy `create_all` on first Postgres store open (no Alembic yet). Acceptable for first demo; schedule migrations before further schema changes.
5. Optional local parity: `docker compose up -d postgres` (dev password only).

---

## Auth behavior

- `APP_PASSWORD` from env/Secret only.
- Production-like `APP_ENV` (`production` / `prod` / `staging` / `railway`) **fails closed** if password unset (process/UI refuses content).
- Development may omit the password (local only — never expose that mode publicly).
- Gate is server-side (`st.stop()` before lab/API content), not CSS/hide-only.

---

## Pre-deploy check (local)

```bash
pip install -e ".[dev]"
APP_ENV=production APP_PASSWORD='(secret)' PROJECT_STORE_BACKEND=postgres \
  DATABASE_URL='postgresql+psycopg://…' \
  UPLOAD_DIR=./data/uploads OUTPUT_DIR=./outputs PROJECTS_DIR=./data/projects \
  python -m scripts.pre_deploy_check

pytest -q tests/unit/test_auth.py tests/unit/test_deploy_paths.py
```

The check script never prints secret values and does not call Railway APIs.

---

## Rollback

1. **App rollback:** Redeploy the previous Railway deployment / image tag (or pin Git SHA) from the Railway dashboard.
2. **Config rollback:** Revert env vars to the last known-good set; keep `*_USE_LLM=false` unless intentionally enabling spend.
3. **Data:** Postgres holds project/run refs; Volume holds file artifacts. Rolling back the app does not automatically restore DB/Volume snapshots — take Railway backups before destructive ops.
4. **Git:** Revert or close the packaging PR; do not force-push `main`.

---

## Acceptance checklist (owner)

- [ ] Draft packaging PR reviewed
- [ ] Written approve to create Railway project + Postgres + Volume (billable)
- [ ] `APP_PASSWORD` Secret set; `APP_ENV` production-like
- [ ] `DATABASE_URL` + `PROJECT_STORE_BACKEND=postgres`
- [ ] Volume mounted at `/data` (or equivalent env paths)
- [ ] All `*_USE_LLM=false` / `LITERATURE_LIVE_RETRIEVAL=false`
- [ ] No public URL until auth verified (login blocks lab + API Settings)
- [ ] Smoke: save project → restart service → reopen refs + re-upload CSV
- [ ] Separate approve before enabling any paid LLM keys

**Stop for owner final approve — no merge/deploy from this packaging task alone.**
