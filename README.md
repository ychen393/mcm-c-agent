# MCM C Research Lab

## Guided research workflow (Draft PR #52 — local evaluation)

The Research Lab now has a six-stage, bilingual user path:

1. Understand the problem and record constraints.
2. Inspect and compare uploaded datasets (the gold/Bitcoin joint chart requires explicit confirmation).
3. Review research candidates, evidence gaps and **manually approve H1**.
4. Run an **offline deterministic historical CSV backtest** or explicitly choose a synthetic demo, with source fingerprints.
5. Re-upload the exact same historical files for sensitivity tests and **manually approve H2**.
6. Build a traceable paper/LaTeX draft, download .tex/.bib files, and **manually approve H3**.

For the historical 2022 MCM C path use files named LBMA-GOLD.csv (Date, USD (PM)) and BCHAIN-MKPRU.csv (Date, Value). The gold/Bitcoin data are user-supplied, *not* independently verified from an online market provider. Raw uploaded bytes and merged rows are deliberately not stored; a reopened run requires reuploading original files to continue. Only historical dataset hashes and compact result artifacts are persisted.

**Important:** The backtest currently supports a fixed set of transparent deterministic baseline strategies. This is a reproducible experiment workbench, not a proof of an optimal trading strategy. The paper is a grounded **outline/draft**, not an automatically submission-ready MCM solution. Live trading, arbitrary generated Python code, automatic approvals and production hosting are not provided.

**Windows Terminal/UI acceptance:** see [docs/UX_GUIDED_RESEARCH_ACCEPTANCE.md](docs/UX_GUIDED_RESEARCH_ACCEPTANCE.md). Run the tests on the PR branch, keep paid LLM options disabled, inspect the app and approve the PR only after local acceptance.

---

A semi-autonomous multi-agent research workspace for exploring MCM Problem C. The system is designed to support evidence-based problem decomposition, data analysis, modeling, validation, and LaTeX paper preparation.

> **Historical checkpoint (2026-11-05):** The M0.5/Phase A–B status text below describes earlier milestones; for the active guided-workflow evaluation see Draft PR #52 and the acceptance document above.

## Product principles

- **Evidence first:** numerical claims must be backed by executable artifacts.
- **Independent exploration:** EDA and literature research run as separate branches.
- **Reproducibility:** preserve dataset versions, code, parameters, and experiment outputs.
- **Human oversight:** require approval at major research gates.
- **No fabrication:** never invent data, papers, citations, or experiment results.

## Architecture

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Orchestration | LangGraph |
| LLM | Provider adapters: OpenAI-compatible endpoints and Anthropic |
| Database | PostgreSQL + pgvector |
| Data science | Pandas / NumPy; optional SciPy and scikit-learn |
| Testing | Pytest |
| Paper output | LaTeX (later milestone) |

## Quick start

### Requirements
- Python 3.11+
- Docker Desktop or Docker Engine
- API key for a supported model provider (only needed for live LLM calls)

### Install
```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Configure
```bash
cp .env.example .env
```
Edit `.env`. For DeepSeek, set `LLM_PROVIDER=deepseek`, a model ID enabled for your account, and `DEEPSEEK_API_KEY`. Never commit `.env`.

### Start PostgreSQL
```bash
docker compose up -d postgres
docker compose ps
```

### Test and run
```bash
pytest
streamlit run app/main.py
```

### Railway packaging (not provisioned from this repo)
Container and env contracts live in `Dockerfile`, `railway.toml`, and [docs/RAILWAY_DEPLOY.md](docs/RAILWAY_DEPLOY.md). Do not create Railway resources or public URLs until the owner approves; set `APP_PASSWORD` and `PROJECT_STORE_BACKEND=postgres` for any production-like deploy. Demo without paid LLM: keep all `*_USE_LLM=false`.


## M0 scope
- Configuration validation
- Multi-provider LLM adapter interface
- Shared research state
- Minimal LangGraph graph
- PostgreSQL + pgvector local service
- Streamlit project foundation
- Unit tests for core contracts

M1-A in review: deterministic CSV/XLSX loading, dataset profiling, descriptive statistics, quality warnings, correlations, trend/distribution charts, and JSON/Markdown artifacts. Not yet implemented: paper ingestion/RAG, sandboxed Python execution, model validation, LaTeX generation, and reviewer loops.

M1-B.2 Slice 1 adds an in-memory registry for 1–5 CSV/XLSX files with independent profiles and provenance hashes. Slice 2 lets the Research Lab upload those files and show one EDA section per dataset. Neither slice joins files, aligns dates, draws a cross-dataset chart, or makes an extra model call for multiple files. See [Slice 1 dataset bundle](docs/M1B2_SLICE1_DATASET_BUNDLE.md) and [Slice 2 multi-upload](docs/M1B2_SLICE2_MULTI_UPLOAD.md).

See [Project Structure](docs/PROJECT_STRUCTURE.md), [Development Plan](docs/DEVELOPMENT_PLAN.md), and [M0 Acceptance](docs/M0_ACCEPTANCE.md).

## Safety
Future agent-generated Python must run in an isolated worker. Never execute untrusted generated code inside the Streamlit process or directly on the host.
