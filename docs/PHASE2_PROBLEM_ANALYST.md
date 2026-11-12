# Phase 2 — Problem Analyst

**Branch base:** Phase 1 tip `cursor/phase1-project-persistence-f8a4` (P0 persistence fixes included).  
**Issue:** [#32](https://github.com/ychen393/mcm-c-agent/issues/32)  
**Constraint:** Draft only. Do not merge to `main`. Do not deploy. Do not modify the research checkpoint.

The two foundation nodes still only record the project and dataset provenance. **Analyze Problem** is a separate LangGraph step.

## What a successful run is

`datasets_recorded` → `problem_analysis_running` → `problem_analysis_ready`

The stored `ProblemSpecification` (`schema_version`: `problem-specification-v1`) cites verbatim evidence. Official numbers must appear in the problem text. Proposed modeling directions stay `proposed` and are not confirmed facts. `analysis_status` is not set to `complete`. No trades, joins, or H1 approval are recorded.

`llm_analysis_complete` is true only after a configured provider returns a specification that passes validation.

## What failure and “no model” mean

| Status | When | What the UI does |
| --- | --- | --- |
| `blocked` | No provider, placeholder model, or missing API key | Warning. Datasets stay. Not a completed analysis. `billed_calls` is 0. |
| `failed` | Provider error, or JSON still invalid after the initial call plus 2 repairs | Error and the reason. Datasets stay. |
| hidden | Problem text, files, project id, or model revision changed | Previous specification is not shown as current. |

The same foundation signature and revision notes do not call the provider again.

The deterministic parser in `agents/offline_problem_parser.py` is a test fixture. Its `generation_mode` is `offline_fixture` and `llm_analysis_complete` is false. The product does not use it when the model is missing.

## 2022 C fixture

`tests/fixtures/problem_c_2022_excerpt.txt` states the cash, window, gold trading-day rule, daily bitcoin, 1% and 2% commissions, no look-ahead, terminal value and justification, sensitivity, and memorandum. Tests reject those figures when the text does not contain them.

## DeepSeek smoke (not CI)

One manual call. Check DeepSeek’s current price card first. A single structured reading of the excerpt is the whole smoke; do not loop it. CI does not set the flag and does not call the provider.

```bash
PROBLEM_ANALYST_SMOKE=1 DEEPSEEK_API_KEY=... LLM_MODEL=deepseek-chat \
  python -m agents.problem_analyst_smoke \
  --problem tests/fixtures/problem_c_2022_excerpt.txt
```

Missing flag or key exits 2 and does not call the network. The script performs one `invoke`.
