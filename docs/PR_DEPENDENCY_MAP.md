# Phase 0 — PR Dependency / Merge Order Map

**As of:** 2026-11-12  
**Rule:** Map only. **Do not merge to `main`.** Phase 0 freezes order; owner acceptance gates later merges.

## A. Product research stack (primary)

Linear stack. Prefer fast-forward / stacked merge **in this order** when owner authorizes (not now):

```
main @ c6fbb597f719ebe515bfe1720d511498505040af
  └─ #1  feature/m1a-data-eda                         @ 4ee9a4e49c755dd58d5393822b9ced7741530df5
       └─ #2  feature/m1b-visual-eda                  @ 31bfdb322a86d8f3efe2ea1eb93e4af5794b6efc
            └─ #14 feature/11-dataset-bundle          @ 25455e4fb4af5c971ac7270689caef7662be7748
                 └─ #22 cursor/multi-upload-independent-eda-d360
                        @ cc9f0a448599ed5772b7bc8562f6695bade6323f
                      └─ #25 cursor/slice3-safe-join-preview-a465
                             @ 37dbabcfc8778ed512a4607dbf860db71c7d342f
                           └─ Phase 0  cursor/phase0-unified-baseline-ad8e
                                  (audit + research-state docs on top of #25)
```

| Order | PR | Branch | Depends on | Notes |
| --- | --- | --- | --- | --- |
| 1 | [#1](https://github.com/ychen393/mcm-c-agent/pull/1) | `feature/m1a-data-eda` | `main` | Data loader / EDA foundation |
| 2 | [#2](https://github.com/ychen393/mcm-c-agent/pull/2) | `feature/m1b-visual-eda` | #1 | Visual EDA + API Settings |
| 3 | [#14](https://github.com/ychen393/mcm-c-agent/pull/14) | `feature/11-dataset-bundle` | #2 | Multi-dataset registry |
| 4 | [#22](https://github.com/ychen393/mcm-c-agent/pull/22) | `cursor/multi-upload-independent-eda-d360` | #14 | Multi-file independent EDA UI |
| 5 | [#25](https://github.com/ychen393/mcm-c-agent/pull/25) | `cursor/slice3-safe-join-preview-a465` | #22 | Safe join preview (**selected tip**) |
| 6 | Phase 0 Draft | `cursor/phase0-unified-baseline-ad8e` @ `20c827ba3ffe9b638e209f54743e2cc42d4ee1ad` | #25 tip | Docs + research-state preservation only |

**Phase 0 unified product tip** = checkout `cursor/phase0-unified-baseline-ad8e` (or the SHA recorded in `docs/BASELINE_AUDIT.md` after the Phase 0 commit).

## B. Competing product fork (do not merge into A)

```
#22 @ cc9f0a4  ──┬── #25  (adopted)
                 └── #24 feature/mvp-relationship-20261109 @ 4cab04d
                        (duplicate join/relationship MVP; park)
```

| PR | Branch | Base claimed | Decision |
| --- | --- | --- | --- |
| [#24](https://github.com/ychen393/mcm-c-agent/pull/24) | `feature/mvp-relationship-20261109` | `feature/11-dataset-bundle` (contains #22) | **Park.** Diff vs #25 replaces profiler/schema/panel with alternate module. No naive merge. |

If any `#24` test fixture hardening is desired later, cherry-pick **specific commits** onto the `#25` line after Phase 0 — never merge the whole branch.

## C. Research checkpoint (product lane, docs only)

| PR | Branch | Base | Contents | Phase 0 action |
| --- | --- | --- | --- | --- |
| [#5](https://github.com/ychen393/mcm-c-agent/pull/5) | `docs/mcm-runtime-checkpoint` @ `d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b` | `feature/m1b-visual-eda` | `RUN_STATE`, `NEXT_ACTIONS`, `mcm_checkpoint.json` | **Imported** onto Phase 0 baseline + byte backup under `docs/research-state/backup-2026-11-05/` |

These files existed **only** on the checkpoint branch before Phase 0.

## D. Cursor development / governance stack (separate lane)

Do **not** fold into the product research baseline. Merge order below is for the Cursor-dev collaboration path only, when owner authorizes that lane:

```
feature/m1b-visual-eda
  └─ #3  feature/m1c-agent-governance          (AGENTS.md, AUTONOMY_POLICY, PROJECT_STATUS)
       … cowork / reviewer / automation drafts …
  related: #7, #9, #10, #16, #17, #18, #19, #20, #21
```

| PR | Intent | Relation to Phase 0 |
| --- | --- | --- |
| [#3](https://github.com/ychen393/mcm-c-agent/pull/3) | Governance contracts | Cursor-dev docs only; not product runtime |
| [#7](https://github.com/ychen393/mcm-c-agent/pull/7)–[#10](https://github.com/ychen393/mcm-c-agent/pull/10), [#16](https://github.com/ychen393/mcm-c-agent/pull/16)–[#21](https://github.com/ychen393/mcm-c-agent/pull/21) | Cowork, reviewer, registry, live view | Keep off product tip |

`AGENTS.md` / `docs/AUTONOMY_POLICY.md` / `docs/PROJECT_STATUS.md` remain on governance/cowork branches until a **separate** Cursor-dev integration milestone (Roadmap Phase X), not Phase 0–1 product work.

## E. Recommended future merge policy (owner-gated)

1. Keep `main` frozen until owner accepts a stacked product promotion plan.
2. Promote **A** bottom-up (`#1` → `#2` → `#14` → `#22` → `#25` → Phase 0 docs) or replace with a single squash from the Phase 0 tip **only** after acceptance.
3. Close or label `#24` as superseded/parked relative to `#25`.
4. Keep lane **D** PRs targeting their own bases; do not retarget them onto the Phase 0 product tip without a dedicated Cursor-dev plan.
5. Phase 1 (Issue `#26`) starts from the Phase 0 tip SHA after this Draft PR’s evidence is accepted — not from `main`, and not from `#24`.

## F. SHA pin table (audit snapshot)

| Ref | SHA |
| --- | --- |
| `main` | `c6fbb597f719ebe515bfe1720d511498505040af` |
| `#1` head | `4ee9a4e49c755dd58d5393822b9ced7741530df5` |
| `#2` head | `31bfdb322a86d8f3efe2ea1eb93e4af5794b6efc` |
| `#14` head | `25455e4fb4af5c971ac7270689caef7662be7748` |
| `#22` head | `cc9f0a448599ed5772b7bc8562f6695bade6323f` |
| `#25` head | `37dbabcfc8778ed512a4607dbf860db71c7d342f` |
| `#24` head (parked) | `4cab04db2f69e0edc622a3c5f7c32636c4e1c692` |
| `#5` checkpoint head | `d5dd95d0e1ffb802c5f3a87c38184631f99f8c1b` |
| `#3` governance head | `91bf8fdfcdc6588e83c28b1ba9d629a6cfa45a6c` |
| `#24`∩`#25` merge-base | `cc9f0a448599ed5772b7bc8562f6695bade6323f` |
| Phase 0 fixed baseline | `20c827ba3ffe9b638e209f54743e2cc42d4ee1ad` |
