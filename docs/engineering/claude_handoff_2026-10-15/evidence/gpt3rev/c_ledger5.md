**Claude (integration / CI / performance lane) - exact-head release ledger, refreshed 2026-10-16 (main = `cfc86cb8`).** Every review below is an independent technical review COMMENT or a measurement. **I merged nothing, approved nothing and flipped nothing to ready.** One shared GitHub login (`main` has no protection) means no formal independent approval exists: **B1 - the repository owner merges, or provisions distinct reviewer identities / a required-review ruleset.** No benchmark truth, source PDF, tolerance or denominator was touched by me. **Score unchanged:** frozen development score Lot16 8/27, Maryborough 0/24; four-project score UNPUBLISHED.

## MERGED since the last ledger (all by the owner login, 2026-10-15)
`#2787` (GPT3 signed-output import gate), `#2796` (mine: source PDFs / V2 tree cannot change with production code; pinned PDFs hash-verified), `#2798` (GPT3 fingerprint pins), `#2761` (GPT1 original room-area line first-gate shadow), `#2766` (GPT MAX Lot16 source identity), `#2801` (GPT MAX same-root F07 on clean main), `#2726` (GPT2 W4 shadow, touches `pb_physical_wall_candidate_authority.py`), `#2784` (mine: W2 lineage-attach prefilter, with another agent's overflow fix). Closed unmerged: `#2794`.

## Signed outputs after those merges (original source, `cmp` against the archived signed originals)
Replays dispatched on **`main` `cfc86cb8`**: Lot16 run 38826189304 and Maryborough run 38826192293 - `source_sealed_run.json` and `verified_customer_rows.json` **byte-identical** for both (Lot16 fp `ef58f8ae...` = 8 opening quantities 0.54 / 0.9 / 1.26 / 1.8 / 1.8 / 2.16 / 2.16 / 10.08 m2; Maryborough fp `9f3ab9ac...` = 3 FIRM floors 13.270425 / 9.05352 / 25.37875 m2). The artifact pinned by #2812 (`11929406140`, ZIP SHA `950e1074...`) is also byte-identical to the Lot16 original.

## READY FOR TECHNICAL REVIEW (technically eligible; B1 for every row)
| PR | exact head | base | Actions | notes |
|---|---|---|---|---|
| #2738 GPT1 | `6c6def6b` | `main` | 20 pass / 2 skipped | **both open items closed** (rotated-page test: 90 accepted, 270 abstains; rebase re-run: `original-lot16`, `original-maryborough-retention`, `maryborough-core`, both GPT3 signed replays green); 33 tests pass. APPROVE-RECOMMENDATION |
| #2770 -> #2771 GPT MAX | `97d0e3bb` -> `7fa63407` | `40d8e849` | 27 / 27 | merge #2770 first; **#2805 conflicts with #2771** (6 stage-A hunks; union resolution proven, 121 tests) |
| #2805 GPT2 | `37cd1a91` | `fbaaa518` (stacked) | 8 pass | opt-in W2 `complete_link_snap_shadow`; default path byte-identical to PR base on Lot16 and Maryborough; reviewed |
| #2806 GPT2 | `4d4bca64` | `980b0b18` | 17 pass / 2 skipped | shadow-only classmethod seam; default expressions untouched; 67 tests; reviewed |
| #2809 -> #2813 GPT MAX (cursor) | `61fcb385` -> `51234a81` | `main` -> stacked | 31 / 24 pass | **#2809 APPROVE-RECOMMENDATION** (flag-off path unchanged by construction; signed replays green). **#2813 NOT yet**: motif census depends on `0.03 x page_span` (viewport-expansion changes the result: span 100 -> 0, >= 150 -> 8 motif walls) and classifies 8 identical collinear genuine pieces as a motif; signed replays did not run (base is not `main`) - retarget after #2809 |
| #2802 -> #2811 cursor | `d87c4a36` -> `ca1ecde6` | `main` -> stacked | 11 pass / 0 (no workflows: base is a branch) | shadow-only, no production importer, 149 tests pass incl. merged with main; APPROVE-RECOMMENDATION, retarget #2811 to `main` after #2802 |
| #2776 -> #2791 -> #2792 -> #2795 -> #2797 / #2803 GPT MAX (shadow stack) | `08e4fc7f` `cfab294f` `ce21ae5c` `4604e471` `565dc727` `34221eee` | stacked | 48 / 3 / 3 / 3 / 3 / 3 | **not promotable** (strict retention failure on hostless existence id); **new: their new workflows list only the parent stack branch under `pull_request.branches`, so they would never run on `main` after merge** (#2814 test catches it); do not cite #2797's F07-G17 correspondence (different snapshot; #2804 supersedes) |
| #2804 GPT MAX | `f35a8a5c` | `gptmax/original-same-root-f07-clean-main-20261015` (= merged #2801) | 3 pass | content OK (18 tests, merged with main); **merge-blocking: it replaces `- main` with its stacking branch in the existing workflow** |
| #2799 GPT MAX | `bf5922dd` | stacked | 3 pass | **close as superseded**: tool and test byte-identical to merged #2801; conflicts with main |
| #2793 -> #2800 GPT2; #2808 GPT1; #2810 GPT2; #2807 GPT MAX | `fbaaa518` -> `2e933e4a`; `dbfd4001`; `8504c4d8`; `e7e80ec7` | | 6 / 6 / 10 / 1 / 8 pass | read-only diagnostics; tests pass on each head merged with main (27 / 26 / 75 / 9 / 17); #2807 artifact re-derived (21 = 6+6+3+1+5, 15 hosts, 9 frames, 8 signed, zero GPT1 candidates) |
| #2812 GPT3 | `6e13e02f` | `main` | 6 pass / 2 skipped | pins the eight-row artifact; **artifact expires 2026-11-13** - commit the four small files instead (owner GPT3) |
| #2773 GPT MAX (shadow) | `dc6dc13c` | `40d8e849` | 16 pass | not eligible for activation (BIFOLD role ABSTAIN) |
| #2747 #2751 #2754 #2758 #2760 #2765 GPT MAX | `7758e0c1` `ca6b3eae` `f564fff0` `5a815fd5` `42e063e9` `9652f1ae` | `40d8e849` | 11 / 8 / 6 / 8 / 8 / 8 | leaf shadow modules; **#2754 has no dedicated tests - requested** |
| #2779, #2786, #2788, #2790, #2777, #2783, #2782 (diag) | | | | read-only diagnostics, reviews posted |
| #2693 #2694 #2695 #2705 #2706 (mine) | `5ee56c40` `45631368` `b5a43303` `318a7e1d` `f4a679c6` | `40d8e849` | 36 / 45 / 11 / 11 / 36 | stack 0.51x CPU / 0.65x RSS on 3Laurel (0.45x with merged #2784); outputs byte-identical; needs GPT1 / GPT3 independent review |
| #2723, #2775, #2789 (mine) | `ffff3ab7` `cb1f6960` | | docs / scripts | FT3 candidate-tier report, profile record, hand-off record |
| #2814 (mine, draft) | `a3922383` | `main` | pending | test-only: every workflow with a `pull_request:` block must still fire for pull requests to `main` (161 pass on main today; mutation-verified) |

## BLOCKED (owner -> required proof)
- **B1 (all merges):** repository owner.
- **#2813 GPT MAX (cursor):** viewport-expansion invariance test, look-alike negative (>= 8 identical collinear genuine fragments), source evidence that the skipped pieces are dimension ticks, retarget to `main` for the signed replays.
- **#2804 / #2795 / #2797 / #2803 / #2791 / #2792 GPT MAX:** put `main` in `pull_request.branches`. **#2799:** close.
- **#2748 GPT MAX:** rebase onto #2771 after #2770 with the parameter-union resolution. **#2754 GPT MAX:** synthetic tests.
- **#2680 GPT3:** latest-head signed / frozen verdict (`a4c3116c`, stale base `057b05dd`, merge-tree clean).
- **#2785 follow-up (GPT1 / GPT3 / owner):** decision on the per-snapshot flat-map store (24 % of Q5446, ~9 % of 3Laurel). I implement nothing until then.
- **#2776 chain:** strict retention failure. **#2638 GPT2** (2 failing source-proof jobs), **#2511** (4 failing, stale).
- **FT3 chain:** OFFICE stays candidate-only (#2731/#2743, #2777, #2783, #2810 agree).

## CONFLICTING / STALE / SUPERSEDED
Conflicting with main: #2649, #1953, #1744, #1481, #1339, #1593, #1844, #1864, #1868 (owners: close or rebase). Stale bases only: #2655, #2640, #2684, #2692.

## New findings this round (measured)
- **Dead-trigger risk in stacked PRs (#2814):** 6 distinct workflow files (`frame-competitors`, `hostless-source-census`, `nine-raw-six-w4`, `f07-g17-scope-join`, `a68-selector-matrix`, `same-root-f07-g17-original`) carried by #2791 #2792 #2795 #2797 #2799 #2803 #2804 limit `pull_request.branches` to a parent stack branch. Merged, they stop running on `main`. #2804 even removes the existing `main` entry.
- **#2813 drafting-motif census:** not viewport-expansion invariant; population-statistical, not per-tick evidence (probe in the PR comment).
- **#2812 time bomb:** the pinned artifact expires 2026-11-13T21:06:46Z.
- **#2799 superseded** by merged #2801; **#2797's F07-G17 correspondence is superseded** by #2804.
- Standing: CI duplication (28 heavy workflows = 402 runner-minutes per production change; 10 run the byte-identical Lot16 page-3 command; analysis in #2789), xdist unsafe (SQLite tests share state), `AGENTS.md` still cites the deleted `scripts/check_benchmark_gold_separation.py`.

## NEXT
Re-verify the 8 + 3 signed outputs after every owner merge that touches a production module; review #2814's CI and any replies; keep this ledger current.
