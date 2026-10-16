**Claude (integration / CI / performance lane) - exact-head release ledger, 2026-10-15, refreshed 20:45 (main = `40d8e849`, unchanged; nothing merged by anyone since #2745).** Everything below is an independent technical review COMMENT or a measurement. **I merged nothing, approved nothing and flipped nothing to ready.** One shared GitHub login (`main` has no protection) means no formal independent approval exists: **B1 - the repository owner must merge, or provision distinct reviewer identities / a required-review ruleset.** No benchmark truth, source PDF, tolerance or denominator was touched. **Score unchanged:** frozen development score Lot16 8/27, Maryborough 0/24; four-project score UNPUBLISHED.

## Signed outputs (original source, byte comparison with the archived signed originals)
Lot16 fp `ef58f8ae...` = the 8 signed opening quantities; Maryborough fp `9f3ab9ac...` = 3 FIRM floors (13.270425 / 9.05352 / 25.37875 m2). `source_sealed_run.json` and `verified_customer_rows.json` are **byte-identical (`cmp`)** to the archived originals at: main-equivalent #2781 head `3167da60` (both projects), #2762 head `e4e78280` (both projects), #2776 head `08e4fc7f` (Lot16).

## MERGED
Nothing new since the last ledger (last merged: #2745 `40d8e849`).

## READY FOR TECHNICAL REVIEW (technically eligible; owner authorization B1 for every row)
| PR | exact head | base | Actions at that head | notes / what I verified |
|---|---|---|---|---|
| #2753 GPT3 | `2b8d4cff` | main | 10 pass | signed-JSON rejection before reconstruction; clean merge-tree |
| #2762 GPT3 | `e4e78280` | main | 11 pass (CI 38695220876, Maryborough 38695221187, Lot16 38695221171) | **final verdict posted**; tree identical to my reviewed `bae21e77`; fresh sealed output byte-identical to the originals; #2769 SUPERSEDED |
| #2770 -> #2771 GPT MAX | `97d0e3bb` -> `7fa63407` | main | 27 / 27 pass | merge #2770 first; default W2-W5 output identical on original pages 7 and 11 |
| #2735, #2732, #2738 GPT1 | `11f84350`, `01092b8b`, `3daefdde` | `b48c3ad6` (stale) | 8 / 8 / 14 pass | merge-tree clean vs current main; rebase re-run required; #2738 measured below |
| #2726 GPT2 | `975c0066` | `7a50a83b` (stale) | 42 pass | merge-tree clean; rebase re-run of the original W4 workflow required |
| #2776 GPT MAX (shadow) | `08e4fc7f` | main | 48 pass | default-path Lot16 output byte-identical; Maryborough replay dispatched (run 38707753061, pending); flag default False; trial-merges clean with every open PR and my stack |
| #2773 GPT MAX (shadow) | `dc6dc13c` | main | 16 pass | shadow only; **not eligible for production activation** (BIFOLD role semantics; #2779 confirms the role stays ABSTAIN) |
| #2747, #2751, #2754, #2758, #2760, #2765 GPT MAX | `7758e0c1`, `ca6b3eae`, `f564fff0`, `5a815fd5`, `42e063e9`, `9652f1ae` | main | 11 / 8 / 6 / 8 / 8 / 8 pass | new leaf shadow modules; no production importer on any head |
| #2766, #2779 GPT MAX (diag) | `74d0ddc8`, `9dc68b8f` | main | 8 / 8 pass | tools/tests/docs only |
| #2772, #2774 GPT2 (docs) | `ed97aeb7`, `4da9747e` | main | 5 / 5 pass | architecture reports; reviewed |
| #2778 GPT3 (workflow) | `47343e58` | main | 7 pass | tightens receipt-retention asserts (identity may not disappear; frame equality) - recommend a mutation test of the gate |
| #2782 GPT MAX (source bytes) | `d6861cf0` | main | 10 pass | adds the structural PDF (SHA `b4025958...`); no code enumerates `documents/sources` except one SHA-matched glob; **owner must confirm provenance of the owner-provided file** |
| #2693 #2694 #2695 #2705 #2706 (mine) | `5ee56c40` `45631368` `b5a43303` `318a7e1d` `f4a679c6` | main | 36 / 45 / 11 / 11 / 36 pass | stack = **0.53-0.55x CPU, 0.64-0.66x peak RSS** on complete 3Laurel and Q5446, outputs byte-identical (table on #2692) - needs GPT1/GPT3 independent review |
| #2781 (mine) - SUPERSEDED by #2787 | `3167da60` | main | 11 pass | contained in #2787; its parser had two silent-pass defects (no PR trigger, inline `paths`) that GPT3 found and fixed; leave draft, merge one |
| #2787 GPT3 (integrated signed-output gate) | `fdaa6f48` | main | 0 pass / 0 pending | contains #2781 + fail-closed fixes (10 tests pass); remaining silent paths (branches/types/job `if`/`continue-on-error`) fixed in my branch `claude/gate-trigger-hardening-20261015` (13 tests, mutation-checked) for GPT3 to cherry-pick; exact-head replays pending, I will `cmp` them |
| #2784 (mine) | `6806a6a8` | main | 14 pass / 0 pending | W2 lineage-attach change: complete-handoff outputs byte-identical to main; CPU 0.935x alone (3Laurel), 0.510x -> 0.448x on top of the stack; Lot16 + Maryborough replays byte-identical on the branch and on the combined stack branch `a8eb952b` (runs 38708678580, 38708673877, 38710205939, 38710210418) |
| #2783 GPT1 (diag), #2777 GPT2 (diag) | `49b3d660`, `3e4cf1b3` | main | 5 pass / 3 pending / 4 pass / 2 pending | read-only diagnostics, tools/tests/workflow only |
| #2786 GPT MAX (diag, stacked on #2782) | `f930ea40` | #2782 head | 5 pass | read-only structural-revision diagnostic; abstains on ambiguous dates, grants nothing; merges only after #2782 |
| #2785 (mine, docs) | `b190ee5d` | main | docs only | architecture report for the derived-snapshot republish (24 % of Q5446); awaiting GPT1 / GPT3 decision, no code |
| #2723, #2775, #2692 (mine, diag) | `2b2af634`, `8833851f`, `d266ca06` | main / stale | 7 / 7 / 8 pass | candidate-tier FT3 report; profile; measurement |

## IN FLIGHT
None of mine. All replays and variant workflows requested today have finished (results above and on #2784 / #2692 / #2776).

## BLOCKED
- **B1 (all merges)**: repository owner.
- **#2748 GPT MAX** `815aaa72`: textual conflict with #2770 and #2771 in one hunk (`_graph` signature in `pb_g17_plan_wall_scope_shadow.py`). Union of the keyword parameters resolves it: on a scratch merge of #2748 onto #2771, 113 tests of both PRs pass. **Owner: GPT MAX** (rebase onto #2771 after #2770 merges).
- **#2638 GPT2** `fb7c7a2e`: 2 `source-proof` jobs fail and it changes a frozen scope dataclass. **#2511** (4 fail, stale). Owners: GPT2 / author.
- **#2680 -> GPT3**: latest-head signed/frozen verdict (`a4c3116c`, base `057b05dd` stale, merge-tree clean).
- **FT3 chain**: unchanged (OFFICE candidate-only); GPT2 (definition 21/24 words, page-11 SourceRoomFace), GPT1 (measurement handoff).
- **#2738 -> GPT1**: its own invariance tests (room order, rotated page, determinism, no-mutation) and rebase re-run.

## SUPERSEDED / CONFLICTING / STALE
- SUPERSEDED: **#2769** (by #2762 head). CLOSED by me: **#2780** (xdist measurement, result below).
- CONFLICTING with main: #2649, #1953, #1744, #1481, #1339, #1593, #1844, #1864, #1868 (owners: close or rebase). Stale bases: #2655, #2640, #2684, #2692 (docs/tools only).

## Integration dry run (scratch tree, no branch pushed except my own stack branch)
Merging #2753 #2762 #2735 #2732 #2726 #2738 #2770 #2771 #2773 #2776 #2747 #2751 #2754 #2758 #2760 #2765, the five performance PRs, #2784 and #2781 onto `40d8e849`: **23 merges, 0 textual conflicts**; the 29 test files those PRs add or change = 664 passed; full `pytest tests/` = 14,748 passed / 19 failed (37 min), and **the same 19 tests fail identically on pristine main in this Windows environment** (symlink-privilege and shallow-history tests), i.e. the combination adds no failure. #2748 is excluded (conflicts with #2770 / #2771).

## Performance and CI findings (measured)
- **Same-runner complete-handoff, byte-identical outputs on all variants:** 3Laurel CPU base 1105.6 s -> stack 604.7 s (0.547x), RSS 6.34 -> 4.19 GB (0.661x); Q5446 549.9 s -> 290.3 s (0.528x), 7.40 -> 4.70 GB (0.635x). **#2738 is neutral** (0.995x / 0.988x; 3Laurel +0.2 % RSS, Q5446 -6.5 % RSS) alone and on the stack (0.546x / 0.530x). Run-to-run noise 0.4-0.8 %.
- **Profile of the stack (py-spy, 3Laurel / Q5446):** 16 % / 3 % in W2 lineage-attach (addressed by #2784); 24 % / 6 % in the opening-proof subtree, about half of it the before/after full-source authentication of `_native_dimension_source_proof_batch` (O(pages x observations)) - **a deliberate integrity gate, not changed by me; candidate for an owner-approved page-scoped proof**; 9 % / 24 % in 22 derived-snapshot commits that each republish ~587k records to add 9-85 new ones (after the first derivation) (store layout; deep authority change, owner decision); ~5 % / 9 % page renders (identical PNG bytes across snapshots).
- **CI queue:** a production change triggers 15-19 path-filtered workflows (up to ~360 workflow-minutes), eight of which replay Lot16 separately; `pytest tests/` is ~90 % of the main CI job (597 s). **pytest-xdist halves it (302 s) but is not parallel-safe**: 6 (3.13) / 13 (3.14) extra failures from SQLite-backed tests sharing state (details on #2780; task raised to isolate the databases). Two every-push workflows (Performance Fastpath CI, TEST GPT3 Raster Schedule Aperture) are strict subsets of the full CI.
- **Gate coverage gap closed in #2781** (pending owner/GPT3 adoption): signed-output replays previously ran for only 12 / 16 of the files the producers can import.

## NEXT
Waiting on owners: GPT1 / GPT3 independent review of the performance PRs and of #2785; GPT3 adoption of the hardening commit on #2787 (supersedes #2781); GPT MAX rebase of #2748; GPT1 items 2 and 4 on #2738; owner merge decisions (B1). Mine: re-verify the 8 + 3 signed outputs after every owner merge; keep this ledger current.
