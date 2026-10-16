**Claude (integration / CI / performance lane) - exact-head release ledger, 2026-10-16 (evening), `main` = `e43d656a`.** Every review below is an independent technical review COMMENT or a measurement. **Formal independent approval still does not exist: the repository has one shared GitHub login (B1).** The merges listed here were made by me on the repository owner's explicit instruction of 2026-10-16 ("clean the repo review, fix and merge anything we need"); each had an independent technical review of the exact head and no open ask, and nothing was merged merely because CI was green. No benchmark truth, source PDF, tolerance or denominator was touched by me. **Score unchanged:** frozen development score Lot16 8/27, Maryborough 0/24; four-project score UNPUBLISHED.

## MERGED this session (in order; each PR carries a merge note)
`#2814` `bb5a97d7` (guard: every `pull_request` workflow must still fire for PRs to `main`), `#2789` hand-off record, `#2775` profile record, `#2723` FT3 candidate-tier report, `#2815` (AGENTS.md names the gate CI really runs, `check_v2_truth_separation.py`), `#2817` (16 root-level scratch files moved to `docs/archive`), then the production batch verified as one tree in the closed vehicle #2816: `#2738` `537cef5d`, `#2809` `4d811f11`, `#2802` `1a305c52`, `#2806` `c41a40a1`, the performance stack `#2693` `a370da9a`, `#2694` `1be9979c`, `#2695` `9be00ebf`, `#2705` `ba44dbe6`, `#2706` `7b3c05e0`, and the W2 integration `#2819` `3f77e42c` (carries #2770, #2771, #2793, #2805; #2805 closed as landed because its stacked base blocked the auto-merge mark). GPT3 merged my suggested patch `#2820` into `#2812`.

## Evidence for the production batch
- Vehicle #2816, head `411c92cd` (`main` `5b3ad289` + 11 PRs, 0 conflicts): **87 checks SUCCESS, 2 skipped (path filter), 0 failing**, `test` on 3.13 and 3.14 green.
- **Signed outputs on that tree:** Lot16 run 38833713575 and Maryborough run 38833713380: `source_sealed_run.json` and `verified_customer_rows.json` **byte-identical** to the archived signed originals (Lot16 fp `ef58f8ae...`, 8 opening quantities; Maryborough fp `9f3ab9ac...`, 3 FIRM floors).
- Q5446 complete handoff, local, `main` against the tree: `production_summary.json` and `source_attempt_preflight.json` identical; 302 s against 647 s (0.47x).
- The nine PRs merged individually in order; the resulting `main` tree `a0783284...` equals the locally verified merge result (GitHub reported a criss-cross conflict on #2706 that git resolves cleanly; I merged `main` into its branch, tree identical, then merged).
- `#2784` overflow regression intact on `main` (2 overflow tests pass, `_PREFILTER_SAFE_ABS_PT` present).
- **Post-merge replays on the integrated `main` (head `37c0028e`, includes `#2819`):** Lot16 run 38839768522 and Maryborough run 38839770970 dispatched; **result to be recorded as a comment on #2608 when they finish** (both replays were byte-identical on the pre-merge trees of #2816 and #2819; the real post-merge tree was also re-tested locally: 286 tests, both gates exit 0).
- 3Laurel complete handoff, local, `main` before the batch (`cfc86cb8`) against after: run `run_3laurel_pair.sh`, result pending at writing (Q5446 pair was identical).

## W2 shadows: ONE Claude-owned integration (requested by GPT2 on #2608)
`#2819` **MERGED** `3f77e42c` (`claude/w2-w3-flags-integration-20261016`, head `2ea5fe60`): #2770 `97d0e3bb` + #2771 `7fa63407` + #2793 `fbaaa518` + #2805 `37cd1a91`, six keep-both hunks, plus an integrator guard: `complete_link_snap_shadow` is rejected together with the exact source-incidence shadows (mutation-checked: disabling the guard fails exactly the four exclusivity tests). 24 integration tests, 145 across the nine changed test files. **Typed residual pinned:** the greedy complete-link assignment is input-order sensitive when one endpoint is within tolerance of two incompatible nodes (b between a and c). Original Maryborough page 7 counterfactual (GPT2 job, artifact of this head): 24,516 retained endpoint samples, 1,206 running-centroid joins rejected, **5,766 -> 5,962 W2 nodes (+196)**, all source items preserved, diagnostic only. Exact-head evidence: 34 checks SUCCESS, 2 skipped, 0 failing; Lot16 run 38836521876 and Maryborough run 38836521638 byte-identical to the archived originals. #2748 (GPT MAX) needs one union hunk in `_graph`: resolved and tested (258 tests pass), commit `3f16d508` on the pushed branch `claude/union-2748-on-w2-20261016`; instructions posted on #2748.

## OPEN, technically reviewed (exact heads; B1 for every row)
| PR | head reviewed / current | state |
|---|---|---|
| #2813 GPT MAX/cursor (stacked on merged #2809) | reviewed `13cc46d1`; current `fb565a1b` | my three residual asks addressed (sparse motif pinned, skipped fragments named in reason codes, perpendicular ticks documented); that commit (`e614c0d0`, an unconditional change to `source_record_from_segment`) was **reverted at `c732cfa8`, hold lifted**; my local Lot16 page-3 differential with it present was byte-identical to `main` (informational). Exact-head signed replays still queued at `c732cfa8` |
| #2811 cursor | `ca1ecde6` | retargeted to `main` and reopened to start CI; shadow-only, 149 tests |
| #2812 GPT3 | reviewed `0adc1d89` | **merged into `main` by GPT3 (`f384691d`) after my review**: fixture from #2820, bytes verified, 9 tests, 8/27 replay reproduced; exact-head CI was green (6 SUCCESS) |
| #2754 GPT MAX | reviewed `7421e26d` | my test request closed (12 cases); leaf shadow |
| #2810 GPT2 | reviewed `d29badc1`; current `f488cf91` | ranked D4/scale/competing registrations retained, 69 tests, all authority flags False; `push` trigger lacks `paths` |
| #2783 GPT1 | reviewed `e958a387`; current `d3b7283a` | stricter trust boundary, 20 tests |
| #2818 GPT2 | reviewed `ba77df37`; current `4adfac89` | docs; OFFICE stays ABSTAIN, three signed floors preserved |
| #2821 GPT1 | reviewed `8f31a000` | **2 of 43 tests fail on this head (`1 != True`, `1 != 1.0` in the test)**; strict-xfail finding reproduced; guard PR **#2826** open (CI running) |
| #2791 `6e14def0`, #2792 `4a08c9dc`, #2795 `14a5d1b1`, #2797 `8359938c`, #2803 `510ab497`, #2804 `42da2509` GPT MAX | stacked diagnostics | **trigger repairs verified** (`main` added to `pull_request.branches` on every changed workflow; the #2814 guard passes on each); still stacked on the unpromotable #2776 chain except #2804 |
| #2793 `fbaaa518`, #2800 `2e933e4a`, #2808 `dbfd4001`, #2807 `e7e80ec7`, #2790 `473ce094`, #2788, #2777, #2779, #2782, #2786, #2773, #2747, #2751, #2758, #2760, #2765 | read-only diagnostics / leaf shadows | reviews posted earlier; unchanged unless noted |

## BLOCKED (owner -> required proof)
- **B1 (all formal approvals):** repository owner (distinct reviewer identities or a required-review ruleset).
- **#2813:** exact-head signed replays on `c732cfa8`; batch documentation pushes (each push enqueues ~36 original-source runs). **#2748:** rebase onto #2819 with the union (prepared). **#2821:** fix the two test cases; then my guard PR removes the strict xfails' reason. **#2680:** GPT3 latest-head verdict. **#2785:** decision on the per-snapshot flat-map store (24 % of Q5446, ~9 % of 3Laurel); I implement nothing until then. **#2776 chain:** strict retention failure. **#2638, #2511:** failing source-proof jobs.
- **FT3 chain:** OFFICE stays candidate-only (#2810, #2818, #2806, #2777, #2783, #2723 agree).

## CLOSED this session (branches kept, reopenable)
Stale and conflicting (590-760 commits behind): #1339 #1481 #1593 #1744 #1844 #1864 #1868 #1953. Superseded: #2799 (content landed in #2801), #2692 (measurement done), #2816 (verification vehicle, results above).

## Clean-up done (not changing any code)
98 worktrees and 124 merged local branches removed (clean and fully pushed only), 63 remote branches of merged PRs deleted (never a stacked PR's base), primary checkout back on `main`, `.chatgpt-worktrees/` locally ignored, `scripts/` and the hand-off in `docs/engineering/claude_handoff_2026-10-15/`. Kept on purpose: about 105 worktrees that are dirty, hold unpushed commits or belong to another lane (listed in the hand-off).

## Findings this round
- **Dead-trigger pattern** in stacked workflows (fixed by GPT MAX, guard #2814 in `main`). **#2812 artifact expiry 2026-11-13** (fixed by the committed fixture). **#2813 lineage change** outside shadow scope. **#2821 test defect** and a real missing guard in `build_gross_wall_area_quantity` (no production caller today). **Runner queue:** 85 queued runs at peak; I cancelled queued runs on superseded heads (script `cancel_stale_queued.py`).
- Standing: CI duplication (402 runner-minutes per production change), xdist unsafe, 19 environment-dependent failures on this Windows machine.

## NEXT
Record the post-merge replays (Lot16 38839768522, Maryborough 38839770970) and the 3Laurel pair; read #2826's and #2813's checks; keep re-verifying the 8 + 3 signed outputs after every owner merge that touches a production module.
