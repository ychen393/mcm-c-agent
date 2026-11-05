# Agents

Agent implementations are introduced incrementally as vertical slices with typed contracts and deterministic fallbacks.

## Implemented / in development

- **Visual EDA Planner (Phase B):** receives the MCM C problem statement and deterministic dataset profile; proposes a ranked ChartPlan using the configured Multi-LLM adapter. Its output is validated against the real DataFrame before human approval and Python execution.
- The planner never writes or executes Python, invents columns, or computes statistics.
- If the problem statement is absent, the provider is unavailable, or the plan fails validation, the application retains a clearly labeled generic deterministic EDA fallback.

## Planned later agents

- Problem Analyst
- Literature / Evidence Researcher (after source and competition-compliance gates)
- Research Strategy / Debate Critic
- Insight Analyst and EDA Reviewer (Phase C)
- Model Builder and Validator
- Paper Writer and Reviewer

All agents must use versioned Pydantic contracts, record provider/model and prompt version where applicable, and preserve evidence provenance.
