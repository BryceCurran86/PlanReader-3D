**Verification vehicle - do not merge this PR.** It exists only so that the full path-triggered CI (both signed-output replays, `maryborough-core`, the GPT MAX / GPT3 source jobs, `test` on 3.13/3.14) runs on the exact tree that will result from merging the PRs below onto `main` `5b3ad289`, in this order. Each PR is then merged individually in the same order, so the resulting tree is identical.

Order: #2738 (GPT1 same-source F07 scale scope), #2770, #2771 (GPT MAX opt-in W2/W3 shadow flags), #2809 (opt-in split-centreline frame shadow), #2802 (annotation-cycle shadow, no importer), #2806 (GPT2 floor-finish shadow seam), then the performance stack #2693, #2694, #2695, #2705, #2706 (byte-identical outputs required).

Local evidence: 11 merges, 0 conflicts; the 17 test files these PRs add or change pass; `check_v2_truth_separation` and `check_full_plan_v2_integrity` exit 0. Gate to merge: this PR's CI green, and the Lot16 / Maryborough signed outputs byte-identical to the archived originals (compared with `cmp` from the replay artifacts).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
