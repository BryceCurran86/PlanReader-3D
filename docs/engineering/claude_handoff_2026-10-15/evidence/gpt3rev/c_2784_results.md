**Evidence for #2784 at exact head `6806a6a8` (W2 lineage-attach throughput change; output-identical).** Measurement and verification only; nothing merged; B1 applies.

**Actions:** `gh pr checks 2784` = 14 pass / 2 skipped by path filter / 0 pending / 0 failing (CI `test` 3.13 + 3.14, `maryborough-core`, `maryborough-grid-component`, `original-source`, focused jobs, and the variant workflow below).

**Complete original-source handoffs, same runner, sequential variants (run 38708678556; every output file of every variant is byte-identical to unchanged main, all runs exit 0):**

| project | variant | code | CPU s (user+sys) | vs main | peak RSS MiB | vs main |
|---|---|---|---|---|---|---|
| 3Laurel | main | `40d8e849` | 919.1 | 1.000 | 6404 | 1.000 |
| 3Laurel | main + this change | `6806a6a8` | 859.3 | **0.935** | 6403 | 1.000 |
| 3Laurel | resource stack (staged GC) | merged tree | 468.6 | 0.510 | 4186 | 0.654 |
| 3Laurel | stack + this change | merged tree | 412.2 | **0.448** | 4189 | 0.654 |
| Q5446 | main | `40d8e849` | 559.5 | 1.000 | 7575 | 1.000 |
| Q5446 | main + this change | `6806a6a8` | 543.1 | 0.971 | 7048 | 0.930 |
| Q5446 | resource stack | merged tree | 300.3 | 0.537 | 4785 | 0.632 |
| Q5446 | stack + this change | merged tree | 296.6 | **0.530** | 4780 | 0.631 |

So the change is worth 6.5 % of CPU on its own and about 12 % on top of the stack on 3Laurel (0.510 -> 0.448), ~1-3 % on Q5446, where W2 lineage is only ~3 % of the run. The runner was faster than in my earlier tables (main 919 s here vs 1106 s before); ratios are only comparable within one table.

**Signed outputs (original source, `cmp` against the archived signed originals):** Lot16 replay on this branch (run 38708678580, `producer_head_sha` = `6806a6a8`) and Maryborough replay (run 38708673877): `source_sealed_run.json` and `verified_customer_rows.json` are **byte-identical** for both (Lot16 fp `ef58f8ae...` = 8 quantities, Maryborough fp `9f3ab9ac...` = 3 FIRM floors).

**Shipping combination:** main + #2693 + #2694 + #2695 + #2705 + #2706 + this change on `claude/resource-stack-integration-20261015` (head `a8eb952b`): Lot16 replay run 38710205939 and Maryborough replay run 38710210418 are both byte-identical to the archived originals.

**Interaction with every other open PR (integration dry run, scratch tree):** merging #2753 #2762 #2735 #2732 #2726 #2738 #2770 #2771 #2773 #2776 #2747 #2751 #2754 #2758 #2760 #2765, the five performance PRs, this PR and #2781 onto `40d8e849` gives 23 merges with 0 textual conflicts; the 29 test files those PRs add or change = 664 passed; full `pytest tests/` on that tree = 14,748 passed, 19 failed in 37 min, and **the same 19 tests fail identically on pristine main in this Windows environment** (symlink-privilege and shallow-history tests), so the combination adds no failure.

Eligible for independent review by GPT2 / GPT MAX (W2 lineage owners); release blocked only by B1.
