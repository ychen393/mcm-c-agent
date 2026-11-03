# Architecture Decisions (M0)

1. Start as a modular monolith; avoid microservices until needed.
2. Use LangGraph for orchestration and typed shared state.
3. Keep LLM provider configuration outside agent implementations.
4. Keep deterministic tools separate from reasoning agents.
5. Use local Docker PostgreSQL with pgvector for reproducible development.
6. Run generated Python in an isolated worker, never inside Streamlit.
7. Keep raw uploads and generated outputs out of Git.
8. Use explicit human approval gates for major modeling and paper decisions.
