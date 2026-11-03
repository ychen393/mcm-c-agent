# MCM C Research Lab

A semi-autonomous multi-agent research workspace for exploring MCM Problem C. The system is designed to support evidence-based problem decomposition, data analysis, modeling, validation, and LaTeX paper preparation.

> **Status:** M0 Project Foundation — scaffold pushed; local runtime and external integrations still require verification.

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

## M0 scope
- Configuration validation
- Multi-provider LLM adapter interface
- Shared research state
- Minimal LangGraph graph
- PostgreSQL + pgvector local service
- Streamlit project foundation
- Unit tests for core contracts

Not yet implemented: paper ingestion/RAG, full EDA agents, sandboxed Python execution, model validation, LaTeX generation, and reviewer loops.

See [Project Structure](docs/PROJECT_STRUCTURE.md), [Development Plan](docs/DEVELOPMENT_PLAN.md), and [M0 Acceptance](docs/M0_ACCEPTANCE.md).

## Safety
Future agent-generated Python must run in an isolated worker. Never execute untrusted generated code inside the Streamlit process or directly on the host.
