# Agent fast first-failing-gate loop — 9 November 2026

## Objective

Stop burning a full two-Python (~30,000 tests) CI run and a slow private-original replay on *every exploratory micro-change*. Run a **bounded synthetic/negative test locally after each fix** and reserve the expensive actual original-source and byte-retention proof for a fixed, reviewed release candidate.

## Commands

From the agent's working checkout and source-neutral Python environment, after the lane's tests have been brought onto the branch:

```shell
python -m tools.agent_fast_gate --lane claude-corner
python -m tools.agent_fast_gate --lane claude-pier
python -m tools.agent_fast_gate --lane claude-door-height
python -m tools.agent_fast_gate --lane antigravity-office
python -m tools.agent_fast_gate --lane gptmax-customer
```

The helper refuses missing test files and runs no tests matching `original` or `private`. It uses the existing installed Python packages, does not download anything, and has a default 10-minute timeout. A green result only proves the selected *source-neutral* tests. JSON always declares original verification, signed/customer retention, full dual-Python CI, frozen120 score and release authorization **false**, including on a pass.

## Faster production workflow

1. Claude: isolate **one real 3Laurel external door** whose A0.4/A0.5 elevation face matches its source-owned A0.3 opening and establish a bounded identity/kind/host gate. Owner's 2100 assumption is for a provisional review estimate only, never an inferred source height or automatic FIRM. Keep false external-door identities from the earlier map uncredited. Independently, the corner slider already has one authentic two-figure label; host/frame is its first missing authority.
2. AntiGravity: fix the **one verified Maryborough source custody failure** first: 4 synthesized `primitive_cross_sheet_wall_*` IDs must be replaced by actually decoded source-owned page-7 wall primitives with real W4/physical-face correspondence, or ABSTAIN. Reuse original code path; do not spend time adding another room graph or numerical area test.
3. GPT MAX: review the first failing authority, source/customer composition, exact-head CI and private original proof after the vertical slice is credible. Reuse the verified protected 3Laurel corner baseline (head `4c5ede86e`), rather than rerunning it on an unchanged commit.
4. When a candidate is ready, freeze its SHA and run full Python 3.13/3.14 CI, trusted original-positive/negative source replay and Lot16 eight/Maryborough three byte-retention. Never merge only on a fast gate. Four-job official score is separate and remains unpublished until all genuine source/customer/identity gates pass.

This helper intentionally does not change any extractor, scorer, physical rule, signed quantity, customer artifact or original-source file. For an unpublished branch whose lane tests are absent, first cherry-pick/merge only the approved source-neutral test paths; a missing test is not a green test.

## Why faster

The already-verified corner helper completed its private-source test in under a minute **after dependencies and retention**, while the same protected workflow spent over twenty minutes on Maryborough-three byte-retention. A synthetic negative can catch an invalid host or height rule before paying that repeated private verification cost. This is a workflow improvement, not proof of a specific speedup until a subsequent run is timed.
