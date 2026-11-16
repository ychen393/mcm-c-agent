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
