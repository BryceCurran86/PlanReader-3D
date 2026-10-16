# Accuracy levers and shared instructions for all agents (2026-10-16)

**Status.** Planning index and working agreement. `AGENTS.md` and `docs/AI_ENGINEERING_PLAYBOOK.md` win over this file. It does not change any rule, grants no authority, and is not an input to any producer. It was written after the production receipts and the frozen development scoreboard were read *post-producer*; no expected quantity was used, and none appears here. Written by the Claude integration lane from evidence gathered on 2026-10-16 (`main` `e43d656a`); the sources are named per claim so each can be re-derived.

## 1. Why accuracy is hard when the plan set is complete

A full set is easy for a person because a person interprets: reads a schedule, applies a convention, recognises that two views show one room. This system may publish a number only when each link is proven from the drawing's own evidence, so it fails at the weakest link, not at detection.

1. **The PDFs hold lines and text, not walls, doors or rooms.** One Maryborough page reconstructs to 6,391 segments, 5,766 W2 nodes and 3,467 W4 wall candidates (artifact of the GPT2 FREEZER job on `#2819`); dimension ticks, hatching and symbols look like walls (the motif problem, `#2813`). Some sheets are scans, and in Q5446 the lettering is vector outlines.
2. **A chain of gates, any one of which blocks a quantity.** Scale, viewport, host wall, frame, kind, width/height order. Lot16 has 21 physical openings (`#2807` artifact): 8 are signed; of the 13 unsigned, 6 have no host wall, 3 have a host but no frame, 3 have an unproven door/window kind and 1 has a single figured dimension. The 8 signed ones carry a two-number label (area product); a one-number door callout has no second axis.
3. **Sheets cannot be joined without an identifier.** The Maryborough OFFICE appears on pages 11 and 7; two registrations, (-78, 0) and (-43.92, 0), both fit, and the authenticated viewport crops the room box by 0.48 pt (`#2810`, `#2818`, `#2723`). The join stays candidate-tier.
4. **What is produced is not always what is scored.** Maryborough has three signed FIRM floors yet 0 of 24 matched: the scored items are floor *finish* (tiling), ceilings, doors and windows, and plain floor area does not bind to a finish item without the finish definition and occurrence.
5. **The rules trade recall for precision on purpose** (abstain on ambiguity, never nearest/first, no defaults), and the wall stage can stop early: the Q5446 handoff ends at `physical_wall_candidate_scope_complexity_exceeded` with zero walls (verified locally 2026-10-16; 3Laurel needs its own trace, see `#2655`, `#2680`).

## 2. Ranked levers (items that would become reachable; upper bounds, each still needs identity binding)

Scored today: Lot16 27 items, 8 matched; Maryborough 24 eligible items, 0 matched. 3Laurel and Q5446 (the rest of the 120-object suite) produce nothing yet.

| # | Lever | Items | Lot16 / Mary | First failing gate (observed) | Suggested lane (lane owners decide) |
|---|---|---:|---|---|---|
| 1 | Room floor and ceiling areas with the finish bound | 16 | 0 / 16 | no published `SourceRoomFace` for page 11; FT3 definition abstained; page-9 ceiling plan lacks an independent frame (`#2818`, `#2806`) | GPT2 (rooms/finishes), GPT1 (figured witnesses), GPT3 (signing) |
| 2 | Door areas | 14 | 14 / 0 | one-number callouts have no second axis; 6 of 13 unsigned openings have no host; 3 have no proven kind | GPT MAX (hosts/frames), GPT1 (kind/axes) |
| 3 | Opening counts and window frame areas | 8 | 0 / 8 | complete opening universe / schedule parsing (item 35); gross frame area from marked elevations (`#1291` method) | GPT1, GPT MAX |
| 4 | Lot16 surfaces | 5 | 5 / 0 | needs room outlines; two raked 12-degree ceilings need the pitch applied | GPT2, GPT1 |

Lever 1 splits: 12 items are six rooms (three WC/showers, PWD, airlock, laundry; FT2 floors and WFPB ceilings) that appear not to depend on the page-11 to page-7 correspondence (inference: their finish codes are not the FT3 one that `#2806` abstained on); 4 items are Food Prep and Office (FT3 floors, FPB and grid ceilings), which do. Lever 2 splits by evidence: 7 of the 13 unsigned openings already have a host. Lever 4 is five items: three ceilings, one floor, one tiled floor.

Door heights. The 13-page Lot16 set has no door schedule and no door-height note as text; `2590` and `2100` appear only beside datum labels on pages 4 and 5; internal doors are not on the elevations (inference from the sheet layout). So for the internal doors the height is not stated in the drawings. See the owner decision in section 4.

## 3. Instructions for all agents

**Work selection**
1. Do not start from this table or from a score (`AGENTS.md`, point 4). Use it only to choose which first-failing gate to trace; then run the contract loop: trace, propose, synthetic proof, shadow run, authority review.
2. Report the **first failing authority per object** (the receipt field, not a count), the way `#2807` does. A change is judged by how many objects move past a gate with their identity and receipts intact.
3. Never use item ids, project names, file names or expected quantities as an input, a threshold or a test oracle for production code. Real drawings may reveal failure modes; expected values may not choose algorithms.
4. Abstain on unknown, conflicting, stale or ambiguous evidence. Retain every plausible candidate. Never break a tie by nearest, first or smallest. No scale, height, count or area default is authority.
5. New topology and extraction work starts in shadow mode (default-False, explicit-bool, forwarded only when on). Production-affecting changes need an independent review comment on the exact head.

**Evidence and releases**
6. Every production-module change must keep the historical signed outputs byte-identical: compare `source_sealed_run.json` and `verified_customer_rows.json` from the Lot16 and Maryborough replays with the archived originals (`docs/engineering/lot16_original_signed_eight_row_20261015/` for Lot16; hash-pinned, `* -text`). Do not edit the fixture, the benchmark files, the scorer or the source PDFs in a PR that changes production code (`scripts/check_v2_truth_separation.py` enforces it).
7. Batches of production PRs are verified as one tree: build a throwaway integration branch, open it as a draft "do not merge" PR so the full path-triggered CI runs on the exact result, compare the signed outputs, then merge the PRs individually in the same order and check tree equality (`git rev-parse HEAD^{tree}`). The pattern and scripts are in `docs/engineering/claude_handoff_2026-10-15/` (`HANDOFF.md`; the `scripts/clean/` helpers arrive with `#2827`).
8. Formal independent approval does not exist (one shared login). Post COMMENT reviews; never present a comment or a shared-account review as independent approval; merges need explicit owner authorisation.

**CI and repository etiquette**
9. A workflow with a `pull_request:` block must reach `main` (`branches` containing `main` or no `branches`); `tests/test_signed_output_gate_path_coverage.py` fails any that does not. Stacked PRs must not leave the parent branch as the only entry.
10. Each push to a PR enqueues dozens of original-source jobs and the Actions queue reached 85 runs. Batch commits into one push, do not push documentation edits one at a time while checks run, and leave the head alone until the current head's checks finish. Queued runs on superseded heads can be cancelled with `cancel_stale_queued.py` (`scripts/clean/`, `#2827`); it touches queued runs only.
11. Do not delete or overwrite worktrees or unexplained changes you did not create. Unpushed or uncommitted work (for example an untracked module in a `.claude/worktrees/` tree) belongs to its author.
12. Coordination: post lane status and evidence on `#2608`; the Claude lane keeps the exact-head release ledger there and on `#2004`. State exact heads, the evidence you read, and the remaining blocker with its owner.

## 4. Decisions needed from the owner

- **Door-height convention (lever 2).** Either keep abstaining on doors whose height the drawings do not state, or approve, per project and recorded as such, a documented standard door height under the existing `USER_APPROVED` authority type. It must be an explicit, reviewable record (source, scope, who approved), never an inferred or AI default. Until this is decided, agents must not implement a default.
- **Reviewer identities (B1).** Distinct reviewer identities or a required-review ruleset so that independent approval can exist.

## 5. Benchmark observations that must not influence implementation

The lever sizes come from item names and families of the frozen development scoreboard (trade and unit only) and from production receipts. Expected quantities, tolerances, denominators and identity maps were not read for this document and must not be used to choose a method, a threshold or a test oracle. Scores are reported after the producer is frozen.

## 6. How to recompute this

- Lot16 missed items: run the replay step of `.github/workflows/diag-gpt3-full-v2-current-development-checkpoint.yml` against the committed fixture (it writes `failure-ledger.json`).
- Opening gates: `tools/diag_gptmax_lot16_host_frame_gpt1_handoff.py` (`#2807`), field `first_remaining_gate` per decision.
- Maryborough scored families: `benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_maryborough_service_station/reference_takeoff.json`, read for `trade_category`, `unit` and `denominator_eligible` only.
