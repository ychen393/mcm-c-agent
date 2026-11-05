# Agents

Agent implementations are introduced incrementally as vertical slices with typed contracts and deterministic fallbacks.

## Phase B — Visual EDA Planner

- **Implementation:** `agents/visual_eda_agent.py` exposes `plan_visual_eda()`.
- **Inputs:** MCM problem statement, EDAReport profile, and actual DataFrame for deterministic validation.
- **LLM context:** problem statement, compact dataset metadata / column profiles / quality warnings / correlations, and ChartPlan JSON Schema. Raw dataset rows are not sent.
- **Output:** ranked Pydantic ChartPlan with analytical roles, relevance scores, rationale, skipped reasons, provider/model and prompt-version provenance.
- **Recovery:** one bounded repair attempt for malformed or invalid output; deterministic generic EDA fallback for missing problem statement, provider errors or repeated invalid output.
- **Safety:** the model proposes chart specifications only. It cannot provide executable code or calculate metrics. Python validates source columns, chart types, sample sufficiency and declared units.

The planner service is connected to the Streamlit Dataset Explorer through an explicit opt-in, ranked plan preview and mandatory approval gate. Mocked-LLM tests cover provider and validation failure paths.

## Planned later agents

- Problem Analyst
- Literature / Evidence Researcher (after source and competition-compliance gates)
- Research Strategy / Debate Critic
- Insight Analyst and EDA Reviewer (Phase C)
- Model Builder and Validator
- Paper Writer and Reviewer

All agents must use versioned Pydantic contracts, record provider/model and prompt version where applicable, and preserve evidence provenance.
