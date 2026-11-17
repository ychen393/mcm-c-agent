# Guided research workflow — local acceptance (2026-11-16)

This document is the local Windows/PowerShell acceptance checklist for **Draft PR #52**.
The code is on feature branch feature/ux-guided-research-workflow-20261116;
do **not** merge, reset, or modify main as part of this check.

## Safety / state protection

- First check git status --short. Stop and preserve any uncommitted work before switching.
- Existing .env, data/projects/, API credentials, datasets, Postgres volumes and approval history must not be deleted.
- The app is offline/deterministic for modeling and validation; live LLM checkboxes may trigger paid provider calls in **other** panels. Leave those unchecked during acceptance.
- No hidden H1/H2/H3 approval; each hard gate requires an actual human decision.
- Dataset input bytes are not stored in project persistence. Re-upload matching files when reopening a run.

## Terminal verification (PowerShell)

Run inside your existing repository; **do not** run git clean, reset --hard, or any database migration for this acceptance.

~~~powershell
git status --short
git fetch origin
git switch feature/ux-guided-research-workflow-20261116
git pull --ff-only origin feature/ux-guided-research-workflow-20261116
python -m pip install -e ".[dev]"
python -m pytest -q
python -m streamlit run app/main.py --server.port 8502
~~~

Open http://localhost:8502 in a browser after the server is ready.

## Human-readable research + revision acceptance (Nov 17, 2026)

The previous acceptance screens were too technical. The following flow must now pass:

1. **Problem analysis (2022 C):** The page shows a bilingual, beginner-readable five-step plan. Each step answers WHY, WHAT INPUTS, EXACT ACTIONS, OUTPUT and HOW TO CHECK. Canonical extracted English schema is available in advanced details, not the main explanation.
2. **EDA (Stage 2):** For both uploaded price files separately, inspect price, observed quote-return distribution, historical drawdown and trailing volatility. Under **each chart**, locate four separate answers: how to read it, numbers actually found in *that upload*, modeling inspiration, and the next experiment to verify. No fabricated findings or future-price filling.
3. **Hide noise:** Dense dataset IDs, relationship schemas and problem-aware JSON are behind optional advanced expanders. The primary **Finish EDA · Save and continue** action remains visible without opening technical details.
4. **Research plan (Stage 3):** The first visible section clearly says which direction to test first, its concrete implementation steps, shortcomings, how to test it, and alternative approaches. Historical EDA evidence is linked to the decision. An idea that has not been coded is labeled a research hypothesis.
5. **Write actual H1 feedback:** Start the offline research team and attach the proposal. In H1, enter e.g. “Consider a no-trade band because the 2% Bitcoin commission may erase small gains. Specify how gold market closures affect trades and validate on later unseen dates.” Click **Request revision (H1)**. Feedback must be at least 12 characters and is durably recorded with H1=revision_requested.
6. **No unauthorized LLM calls:** A revision-request click alone **must not call the provider**. Returning to Stage 3 shows the exact saved human feedback and a clear re-run action. Clicking without explicitly accepting the two model calls must do nothing to the research proposal.
7. **True re-run:** When the user ticks the separate two-call consent and clicks **Regenerate from feedback**, the configured LLM must revise an existing candidate and a second independent LLM call must criticize that actual revision. If either call fails or output is invalid, preserve the old proposal and revision_requested status (no silent deterministic substitute).
8. **Compare before approving:** Display human feedback verbatim, original proposal, revised proposal, explanation of changes, independent criticism and next tests. Persist revision history (without raw CSV rows); reset H1 to pending and invalidate stale experiments/H2/H3. Only explicit manual H1 approval can open modeling.
9. **Cost/testing:** All automated tests use fake LLM providers. No paid model API or Cloud Agent should be invoked by CI or routine UI navigation. Human can separately test a real provider after opting in.

## User-feedback regression (Nov 16, 2026)

The following specific UX failures must be verified separately:

- **Problem Analyst:** after initialization, choose offline analysis or explicitly enable the configured LLM. Confirm the in-depth 2022 C explanation, task work packages, model families and risks are readable in both Chinese and English. The English raw schema remains under an advanced expander and must never be mistaken for a translated answer.
- **EDA:** select Stage 2 with Previous/Next buttons. Two uploaded historical datasets should each show price, quote-return distribution, drawdown and rolling-volatility charts, with explanations of **what the chart means for modeling**. Inspect missing/duplicate dates. Charts derive from observed rows and are not automatically translated into investment claims.
- **Data handoff:** use the Stage 2 action to record compact EDA findings and move to Stage 3. Confirm model candidate notes cite observed volatility/drawdown and per-file SHA-256 provenance; no raw data rows are saved in ResearchState.
- **Research collaboration:** Stage 3 must expose the workflow Problem Analyst → EDA Specialist → Research Strategist → independent Debate Critic → manual H1. Click the team button and read both the proposed route and critical findings; literature is helpful but not a hard prerequisite once EDA is recorded.
- **Optional actual LLM collaboration:** the extra live Strategist/Critic checkbox is **OFF by default**. It will make **two provider API calls** only if the user explicitly opts in and clicks Run; do not activate for free/offline acceptance. The live text is advisory and never auto-approves H1.
- **Navigation:** Previous/Next browses stages, but cannot fake a completed EDA or bypass H1/H2/H3. Re-running problem analysis invalidates stale downstream approvals and should persist the new specification for the following stage.
- **Human boundary:** a recommended candidate method may be a research hypothesis rather than runnable code. Validate its actual strategy implementation before accepting modeling conclusions.

## Research workflow acceptance — 2022 MCM Problem C

1. **Understand the problem:** create a new project ID; paste the problem statement and initialize. The first user stage should describe the problem specification.
2. **Explore data:** upload LBMA-GOLD.csv (columns Date, USD (PM)) and BCHAIN-MKPRU.csv (Date, Value). Inspect per-file EDA and missing gold quotes. Preview a safe **Inner / Date = Date** join and confirm it. Only then click **Plot joint analysis**. The indexed comparison chart must not fill missing gold market days.
3. **Research plan:** review literature/evidence limitations and candidate models; explicitly approve H1 after reviewing risk. Before approval modeling remains blocked.
4. **Modeling:** choose **Uploaded historical CSV**, run the backtest offline, inspect portfolio value, fees, price provenance hashes, and attach the experiment. If intentionally choosing the synthetic demo, output must be explicitly labeled synthetic, not historical.
5. **Validation:** using the same uploaded CSV bytes, execute the sensitivity suite, compare scenarios, attach the report and separately approve H2. If either input file is altered, validation should fail closed with a SHA-256 mismatch.
6. **Paper:** after H2, generate the paper outline and LaTeX draft. The data/results sections must contain the actual experiment metrics and provenance; download the .tex/.bib files and manually review them. H3 must remain pending until explicitly approved.
7. **State reopening:** reopen the same project/run, verify saved provenance and H1/H2/H3 decisions; re-upload datasets to continue. A new experiment must invalidate stale H2/H3 approval, and a new validation must invalidate stale paper/H3 approval.

## Honest boundaries

- The historical CSV backtest uses deterministic baseline trading strategies. It is **not** a proof of the globally optimal MCM strategy, and it is not a live trading system.
- The paper output is a source-grounded **draft/outline**, not a contest-ready paper by itself. It must be reviewed and expanded by a human.
- The optional arbitrary-code Python sandbox and production deployment are **not** implemented in this PR.
- A PDF preview requires a local TeX toolchain; .tex/.bib export works without it.
- Joint EDA is ephemeral after explicit confirmation; no merged dataset rows are saved. This specific chart compares the 2022 C gold/bitcoin series.
- Regression tests cover schema contracts, source identities, causality, market calendars, soft/hard gates, and the deterministic model→validation→paper path.
