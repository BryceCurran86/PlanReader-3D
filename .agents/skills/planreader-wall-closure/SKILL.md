---
name: planreader-wall-closure
description: Run and repair PlanReader source-painted wall versus opening classification, remove fabricated exterior protrusions, and validate source-owned room closures around BED 5 WIR BATH LIVING. Uses private local original PDFs and exact-head CI without changing customer quantities or frozen scoring.
---

# PlanReader wall / opening / room closure — AntiGravity

Read the controlling `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, and `docs/engineering/ANTIGRAVITY_RUN_WALL_CLOSURE_4443.md` first.

## Action sequence

1. Inspect live issue #4443, PR #4445, stacked Acacia PRs #4423/#4436/#4437, and coordination #4135. Claim unowned exact functions and worktrees; never force overwrite another agent.
2. Determine the **authorized private local** original plan path and its page index from source packet metadata, not a guessed file. The Acacia original source hash in #4436 is `435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a` and its floor plan is 0-based page index 1. If the file does not exist or the hash differs, ABSTAIN and report the blocker; do not import it into GitHub.
3. In Windows PowerShell from the repo root, run `tools/run_antigravity_wall_closure.ps1` with `-Pdf`, `-PageIndex`, `-OutDir` outside the checkout, and `-ExpectedSha256`. The script runs source-neutral tests plus the existing footprint, native edge-ownership and room-region diagnostics. See full command in the handoff document.
4. Inspect all local PNG and JSON outputs, especially owner-highlighted BED 5 / WIR / BATH / LIVING. Confirm one straight real exterior wall (two fabricated boxes absent), source-continuous physical wall sections, true hosted swing/slider door interruptions, and virtual topology closures only at genuine doors. Retain genuine alcoves, do not split open LIVING/KITCHEN, and do not bill virtual walls.
5. Fix the **first original-source falsifier** rather than smoothing or inventing geometry. Add unit/negative fixtures; re-run focused tests and protected original replay. Require closed bounded non-overlapping room rings and proof of real wall and opening source IDs; otherwise leave ABSTAIN.
6. Push a bounded branch, run required exact-head Python 3.13/3.14 full CI, review source/privacy/sealed lineage and regressions, then merge validated PRs. Coordinate through #4135 and log exact commits and source blockers on #4443.
7. Protect frozen120 (27/24/63/6), 2.5 pt production snap, 20,000 primitive limit, Lot16 signed eight openings, Maryborough signed floors and all private originals. Candidate/source-neutral success never certifies FIRM/customer output.

## Exit condition

Do not stop at writing a report alone: implement, validate, push and merge if the evidence permits. Stop an individual unresolved object at a precise missing source witness (ABSTAIN), document it and advance the next independent task. Do not claim a finished original footprint or room takeoff without original source-positive validation. Never claim this skill itself starts an external process automatically.
