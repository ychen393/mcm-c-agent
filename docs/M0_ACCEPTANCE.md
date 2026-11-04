# M0 Acceptance Checklist

Status legend: Not Run / Pass / Fail / Blocked. Do not mark a test Pass without an execution record.

- [ ] T01: expected directories and files exist.
- [ ] T02: pyproject.toml parses and dependencies install.
- [ ] T03: settings load from environment and runtime directories are created.
- [ ] T04: provider adapter has a clear missing-key failure and supports configured endpoints.
- [ ] T05: ResearchState initializes with required defaults.
- [ ] T06: foundation LangGraph compiles and executes.
- [ ] T07: Docker PostgreSQL + pgvector starts and reports healthy.
- [ ] T08: Streamlit dashboard starts.
- [ ] T09: application state and exceptions are inspectable.
- [ ] T10: unit tests pass.
- [ ] T11: project/run/artifact IDs and schema-version conventions are documented.
- [ ] T12: evaluation case schema and deterministic fixture layout are created.
- [ ] T13: ADR-001 is reviewed and implementation spike tasks are scheduled.
- [ ] T14: secret scanning confirms no real API keys or credentials are committed.

## Reliability design gates
- Persistent LangGraph PostgreSQL checkpointing is not yet active in the M0 scaffold.
- The checkpoint + restart/resume implementation spike is a required M0/M0.5 exit item before M2 workflow design is frozen.
- Agent-generated Python must not execute in the Streamlit or orchestrator process. Sandbox implementation and security tests are required before M3 modeling execution.
- Docker Desktop/WSL2 behavior must be tested on the actual Windows development machine; rootless mode must not be claimed unless verified.

Unit tests use mock configuration and do not call paid APIs. Live LLM smoke tests require a valid key and model ID. Database connectivity, checkpoint recovery and sandbox security must be verified locally and have evidence attached to the test record.
