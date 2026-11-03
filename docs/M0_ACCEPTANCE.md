# M0 Acceptance Checklist

- [ ] T01: expected directories and files exist.
- [ ] T02: `pyproject.toml` parses and dependencies install.
- [ ] T03: settings load from environment and runtime directories are created.
- [ ] T04: provider adapter has a clear missing-key failure and supports configured endpoints.
- [ ] T05: `ResearchState` initializes with required defaults.
- [ ] T06: foundation LangGraph compiles and executes.
- [ ] T07: Docker PostgreSQL + pgvector starts and reports healthy.
- [ ] T08: Streamlit dashboard starts.
- [ ] T09: application state and exceptions are inspectable.
- [ ] T10: unit tests pass.

Unit tests use mock configuration and do not call paid APIs. Live LLM smoke tests require a valid key and model ID. Persistent LangGraph Postgres checkpointing is not yet active. Database connectivity and migrations must be verified locally.
