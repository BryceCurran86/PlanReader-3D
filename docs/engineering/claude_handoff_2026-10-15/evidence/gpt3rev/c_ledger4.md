**Claude (integration / CI / performance lane) - exact-head release ledger, 2026-10-15, refreshed 22:15 (main = `51e92161`).** Every review below is an independent technical review COMMENT or a measurement. **I merged nothing, approved nothing and flipped nothing to ready.** One shared GitHub login (`main` has no protection) means no formal independent approval exists: **B1 - the repository owner merges, or provisions distinct reviewer identities / a required-review ruleset.** No benchmark truth, source PDF, tolerance or denominator was touched by me. **Score unchanged:** frozen development score Lot16 8/27, Maryborough 0/24; four-project score UNPUBLISHED.

## MERGED since the last ledger (all by the owner login)
`#2732` (21:14), `#2753` (21:41), `#2762` (21:42), `#2735` (21:44) - production/customer-verification changes; then `#2772`, `#2774` (GPT2 docs), `#2778` (GPT3 workflow gate), `#2785` (my architecture report; **merged with no review - the report is in the repo, its sections 3-5 are NOT approved**, see the record on #2785). Closed: `#2769`, `#2781` (superseded by #2762 / #2787).

## Signed outputs after those merges (original source, `cmp` against the archived signed originals)
Replays dispatched on **`main` `5bf17f75`** (the four production merges): Lot16 run 38729816679 and Maryborough run 38729820826 - `source_sealed_run.json` and `verified_customer_rows.json` **byte-identical** for both (Lot16 fp `ef58f8ae...` = 8 opening quantities; Maryborough fp `9f3ab9ac...` = 3 FIRM floors). The archived originals also verify cryptographically under the new code. `main` moved to `51e92161` afterwards by three docs and one workflow only (no production file), so nothing further to replay. Also byte-identical at: #2762 `e4e78280`, #2776 `08e4fc7f`, #2784 `6806a6a8`, #2787 `52cc0b85`, the combined stack branch `a8eb952b`.

## READY FOR TECHNICAL REVIEW (technically eligible; B1 for every row)
| PR | exact head | base | Actions | notes |
|---|---|---|---|---|
| #2787 GPT3 (signed-output import gate, contains my hardening) | `ed78cd49` | `40d8e849` | 9 pass / 2 pending | GPT3's two new commits fix real flaws in my hardening (`failure()` step condition, ordered `!main` branch exclusion); mutation-verified on the real workflow; replays pending, prior head's byte-identical |
| #2796 (mine) | `8390f0e8` | main | 1 pass / 4 pending | source PDFs and the whole V2 tree cannot change with production code; pinned PDFs hash-verified (24 tests, mutation-checked); found by mutation: a 1-bit PDF edit passed `check_full_plan_v2_integrity` |
| #2794 GPT3 (combined-main parity gate) | `faa27d37` | `5bf17f75` | 1 pass / 5 pending | review posted: assert the pinned fingerprints (it only prints them), fold into the two existing replays to avoid a third ~25 min run, 3 closure tools missing from `paths` |
| #2726 GPT2 | `975c0066` | `7a50a83b` (stale) | 42 pass | merge-tree clean vs `5bf17f75`; rebase re-run of the original W4 workflow required |
| #2738 GPT1 | `fd882024` | `b48c3ad6` (stale) | 7 pass / 7 pending | new tests close my review item 2 except the rotated-page case; rebase re-run required |
| #2770 -> #2771 GPT MAX | `97d0e3bb` -> `7fa63407` | `40d8e849` | 27 / 27 pass | merge #2770 first |
| #2776 -> #2791 -> #2792 -> #2795 GPT MAX (shadow stack) | `08e4fc7f`, `cfab294f`, `ce21ae5c`, `4604e471` | stacked | 48 / 3 / 3 / 0+3 pending | #2776 default-path Lot16 + Maryborough byte-identical; **not promotable** (strict retention failure on hostless existence id); #2791 / #2792 reviewed, #2795 pending |
| #2773 GPT MAX (shadow) | `dc6dc13c` | `40d8e849` | 16 pass | not eligible for activation (BIFOLD role ABSTAIN, confirmed by #2779) |
| #2747 #2751 #2754 #2758 #2760 #2765 GPT MAX | `7758e0c1` `ca6b3eae` `f564fff0` `5a815fd5` `42e063e9` `9652f1ae` | `40d8e849` | 11 / 8 / 6 / 8 / 8 / 8 pass | leaf shadow modules, no importer; per-PR reviews posted; **#2754 has no dedicated tests - requested**; #2765 stacked on #2758 |
| #2779, #2766, #2786, #2788, #2790, #2777, #2783 (diag) | `9dc68b8f` `74d0ddc8` `f930ea40` `76fc118d` `228fa6b3` `8329960e` `49b3d660` | various | 8 / 8 / 5 / 6 / 11 / 6 / 8 pass | read-only diagnostics; reviews posted (#2786: architectural sheet has six date tokens, all later than the 22/01/26 issue the structural certificate cites; #2777 head moved after my review) |
| #2782 GPT MAX (structural PDF) | `d6861cf0` | `40d8e849` | 10 pass | file SHA and size equal the frozen Lot16 manifest pin; owner confirms redistribution rights |
| #2693 #2694 #2695 #2705 #2706 + #2784 (mine) | `5ee56c40` `45631368` `b5a43303` `318a7e1d` `f4a679c6` `6806a6a8` | `40d8e849` | 36 / 45 / 11 / 11 / 36 / 14 pass | stack 0.51x CPU / 0.65x RSS on 3Laurel, with #2784 0.45x; outputs byte-identical; needs GPT1 / GPT3 independent review |
| #2723, #2775, #2789 (mine) | `ffff3ab7` `cb1f6960` `fbc1510c` | | 7 / 7 / 3+2 pending | FT3 candidate-tier report (new section 3.5), profile + measurement record, hand-off + CI duplication analysis (docs/scripts only) |

**Integration dry run on `5bf17f75`:** all still-eligible PRs above merged in order = **20 merges, 0 conflicts**; the 24 test files they add or change = 461 passed; `check_full_plan_v2_integrity` and `check_provider_gold_isolation` exit 0. #2748 (GPT MAX) is excluded: one signature hunk conflicts with #2770 / #2771; union resolution passes 113 tests (posted on #2748).

## BLOCKED (owner -> required proof)
- **B1 (all merges):** repository owner.
- **#2748 GPT MAX:** rebase onto #2771 after #2770 with the parameter-union resolution. **#2754 GPT MAX:** add the synthetic test matrix.
- **#2738 GPT1:** rotated-page test; rebase onto main and re-run the original workflows. **#2726 GPT2:** rebase re-run.
- **#2680 GPT3:** latest-head signed / frozen verdict (`a4c3116c`, stale base `057b05dd`, merge-tree clean).
- **#2785 follow-up (GPT1 / GPT3):** decision on the per-snapshot flat-map store (24 % of Q5446, ~9 % of 3Laurel). Until then I implement nothing.
- **#2776 chain:** strict retention failure remains the promotion blocker (declared single-event rekey needed). **#2638 GPT2** (2 failing source-proof jobs), **#2511** (4 failing, stale).
- **FT3 chain:** OFFICE stays candidate-only (GPT2 / GPT1 / GPT MAX independent evidence now agrees: #2731/#2743, #2777, #2783).

## CONFLICTING / STALE / SUPERSEDED
Conflicting with main: #2649, #1953, #1744, #1481, #1339, #1593, #1844, #1864, #1868 (owners: close or rebase). Stale bases only: #2655, #2640, #2684, #2692.

## New findings this round (measured)
- **Always-on gate holes (#2796):** a one-bit edit of an original source PDF passed the integrity check; source PDFs, scorer code and `identity_map.json` could change with production code and pass the separation gate. `AGENTS.md` cites `scripts/check_benchmark_gold_separation.py`, which no longer exists (the active gate is `check_v2_truth_separation.py`).
- **CI duplication:** 28 heavy original-source workflows = 402 runner-minutes per production change; **10 of them run the byte-identical command** `diag_opening_wall_face_preservation.py --pdf <Lot16> --page-id 3` (237 min for the 11 workflows sharing that tool). Analysis and consolidation proposal: `docs/engineering/claude_handoff_2026-10-15/ci_replay_duplication_analysis_20261015.md` (#2789).
- **#2778 mutation test:** the old Lot16 retention check let an authenticated opening binding disappear silently; the new one fails it.
- xdist (#2780, closed): 2x faster but not parallel-safe; SQLite-isolation task raised.

## NEXT
Byte-compare #2787 / #2794 / #2796 replays when they finish; review #2793 and #2795 when green; re-verify the 8 + 3 signed outputs after every owner merge that touches a production module; keep this ledger current.
