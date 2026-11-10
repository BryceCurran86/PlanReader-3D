# Historical PR integration audit — 10 November 2026

## Result

Audited all **4,212** PRs from #1 through #4266 at main `81c12b417054d14baf1f08a9ea6c460a5d2152ad`: **2,343** recorded merged, **1,862** closed unmerged, **7** open. This is a fixed historical snapshot. Later PRs, new heads and merges belong to the separate live review and must not be mistaken for this inventory.

**All useful work is not yet certified integrated.** There is positive historical integration evidence for 267 closed-unmerged PRs; 1595 remain a conservative behavior/recovery queue. Archived unmerged work is not treated as delivered. Of the 1,595 unresolved closed PR discussions inspected, 800 have no comments, so no closure rationale can be recovered from that channel. This does not prove each delta should be restored.

The [complete ledger](pr_ledger.csv) records every PR's immutable head, GitHub state, exact comparison category and available closure evidence. The [recovery queue](recovery_queue.md) identifies current priorities. Original branches/PR refs have not been deleted or rewritten.

## Method and evidence limits

1. Read every GitHub pull-list page, 100 per page; page 43 contains 12 and page 44 is empty. PR numbers need not be consecutive because issues share the number space. Asserted 4,212 unique records.
2. Fetched all public PR heads and completed shallow history before checking the 5462 ancestors of the pinned main commit. A shallow checkout must not be used to infer lost work.
3. Checked recorded merge/head ancestry. For remaining deltas, compared all changed-file blobs with current main and main's reachable historical blobs; checked stable commit patch IDs and reverse-patch applicability to the unchanged main checkout.
4. Added-line presence is a search aid only. It does not prove deletions, behavior, call-path wiring, measurement authority, current retention or source validation. Every such row remains in the recovery queue.
5. Read all pages of the 1,595 unresolved closed PR comment threads, with zero retrieval errors. Recorded archival/replacement notes as documentary evidence, never as proof the referenced replacement actually landed. A merged child targeting a non-main branch requires an eventual-main check.
6. Inspected concrete gaps and recovered the files below. No production authority, source PDF, signed fixture, frozen120 denominator/identity/tolerance/evaluator or quantity was changed.

| Comparison category | PRs |
|---|---:|
| `added_lines_present_needs_behavior_review` | 86 |
| `all_nonmerge_commits_patch_equivalent` | 7 |
| `empty_pr_delta` | 1 |
| `every_changed_blob_in_main_history` | 220 |
| `head_in_main_history` | 644 |
| `merge_in_main_history` | 1702 |
| `reverse_patch_applies_to_main` | 20 |
| `unverified_delta_retained` | 1532 |

`every_changed_blob_in_main_history` proves the non-deletion file versions existed in main history; it does not assert they are current or that a later rewrite retained their behavior. `all_nonmerge_commits_patch_equivalent` and `reverse_patch_applies_to_main` are patch evidence. Empty deltas contain no additional work to integrate.

Thirteen earliest GitHub merge commits (#1–#11, #13, #14) are outside current main ancestry. Their app features must be checked against the later imported/reworked application before declaring them lost or restoring obsolete versions. Non-main merged children are separately listed in the queue.

## Recovered work

PR #1744's existing production schedule-binding behavior is present through #1822, but its two real-producer integration tests were absent. Restored the exact test file, including the positive source-owned contained tag and the outside-aperture negative. Local Python 3.12 and Python 3.13: **7 passed each** across the restored tests and existing v2 binding regression suite. Additional exact-head CI results belong in the recovery PR.

Six reports from five closed PRs are retained byte-for-byte under `archived_reports/`, with original heads and SHA-256 in [recovered_files.json](recovered_files.json). These are historical research, **not current instructions, measurements or accepted conclusions**. In particular, the old door-height memo is superseded by the owner's 9 November provisional external-door policy, and a historical permanent-window-abstention recommendation does not override later owner source clarifications or current engineering work. Historical "wait for review" wording is superseded by current AGENTS.md.

| Source PR | Recovered file |
|---|---|
| [#3520](https://github.com/BryceCurran86/PlanReader-3D/pull/3520) | [gptmax_b248_original_horizontal_raster_tile_seam_architecture_20261020.md](archived_reports/pr_3520/gptmax_b248_original_horizontal_raster_tile_seam_architecture_20261020.md) |
| [#3890](https://github.com/BryceCurran86/PlanReader-3D/pull/3890) | [claude_w01_strip_structural_assessment_architecture_20261026.md](archived_reports/pr_3890/claude_w01_strip_structural_assessment_architecture_20261026.md) |
| [#4171](https://github.com/BryceCurran86/PlanReader-3D/pull/4171) | [claude_accuracy_gate_census_report_20261102.md](archived_reports/pr_4171/claude_accuracy_gate_census_report_20261102.md) |
| [#4171](https://github.com/BryceCurran86/PlanReader-3D/pull/4171) | [claude_door_height_owner_decision_memo_20261102.md](archived_reports/pr_4171/claude_door_height_owner_decision_memo_20261102.md) |
| [#4187](https://github.com/BryceCurran86/PlanReader-3D/pull/4187) | [claude_opening_ownership_trace_20261102.md](archived_reports/pr_4187/claude_opening_ownership_trace_20261102.md) |
| [#4191](https://github.com/BryceCurran86/PlanReader-3D/pull/4191) | [claude_maryborough_aperture_trace_20261102.md](archived_reports/pr_4191/claude_maryborough_aperture_trace_20261102.md) |
| [#1744](https://github.com/BryceCurran86/PlanReader-3D/pull/1744) | [test_raster_schedule_opening_binding.py](../../../tests/test_raster_schedule_opening_binding.py) |

## Completion criteria for queued work

For each useful unresolved behavior, trace the current consumer and existing negatives, document replacement evidence or make a bounded current-main transplant, test it, and satisfy any applicable original/source/customer/retention and dual-Python gates. Keep the original PR/head in that handoff. A merge count, closed state, stale approval or archived branch alone cannot close the row.
