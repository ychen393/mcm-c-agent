# Project Structure

- `app/`: Streamlit presentation layer.
- `core/`: shared state, graph orchestration, configuration and routing.
- `llm/`: provider adapters and model factory.
- `agents/`: domain agents (introduced in M2).
- `tools/`: deterministic tools and external execution interfaces.
- `knowledge/`: paper ingestion and retrieval (M1).
- `modeling/`: statistical and mathematical modeling (M3).
- `paper/`: planning, LaTeX rendering and templates (M4).
- `database/`: SQLAlchemy models and repositories.
- `schemas/`: typed input/output contracts.
- `tests/`: unit, integration and end-to-end tests.
- `data/`: local development data; raw user data is excluded from Git.
- `outputs/`: generated artifacts; excluded from Git.
