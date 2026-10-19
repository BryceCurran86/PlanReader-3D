# Cursor — quantity recovery and accuracy integration architecture (2026-10-20)

**Status:** Required `AGENTS.md` first deliverable. Review-only. No production
behavior, FIRM quantity, customer mutation, frozen evaluator change, or score
claim in this document.

## Compliance

Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` (§3 wall-length path, §13
evidence compiler), `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`,
GPT MAX #3342, GPT1 #3346, GPT2 #3344, and the live Lot16 handoff
`tools/diag_gptmax_lot16_host_frame_gpt1_handoff.assess_gpt1_opening_candidates`.

## Observed repository behavior

1. Quantity authority is a **chain**, not a detector score. GPT MAX owns host /
   frame source closure; GPT1 owns measurement seams
   (`resolve_linear_measurement_input`, figured-dimension authority, wall length /
   height quantity builders); GPT2 owns room / finish / wall-identity source
   evidence; GPT3 owns sealing and frozen V2 reconciliation.
2. `assess_gpt1_opening_candidates` already emits per-opening
   `first_remaining_gate` and forces `measurement_published=False`,
   `customer_seal_granted=False`, `opening_count_granted=False`.
3. Historical Lot16 diagnostic baseline (archived, not a live score): 21 physical
   openings, 8 signed areas, 13 unsigned with typed first gates (host / frame /
   kind / figured pair / axes). That baseline may not be used as an algorithm
   input.
4. Door height on inspected Lot16 sheets remains unauthenticated; owner decision
   required before any `USER_APPROVED` height. Cursor will not invent a second
   dimension from width.
5. Cursor PR #3348 adds a shadow G17 flank → local W4 end-reach ledger without
   host grant. #3338 already retains unresolved aligned frame pairs under
   `source_fragment_roles_shadow`.

## Inferences (to test, not facts)

- Host recovery alone can yield zero new firm areas if frame, kind, or axes still
  abstain.
- Maryborough finish quantities need GPT2 room/finish closure; Cursor integrates
  handoffs, it does not replace GPT2 producers.
- Completeness of an opening **universe** is independent of any single opening’s
  figured area.

## Proposed Cursor batch sequence (separate focused PRs)

| Batch | Mission items | Deliverable | Authority |
|---|---|---|---|
| A0 | (this review) | Architecture doc | none |
| A1 | 1, 23, 24 | Opening inventory + signed-ID immutability + duplicate/stale rejection shadow | diagnostic |
| A2 | 2, 8 | Wire G17 end-reach ledger into unhosted flank census | diagnostic |
| A3 | 3, 4 | Typed unproven frame-pair SAME/DISTINCT/AMBIGUOUS ledger | diagnostic |
| A4 | 9–11 | Kind / label / axis ownership fail-closed helpers (reuse GPT1 seams) | shadow |
| A5 | 14–15 | Opening-universe completeness + dedupe without merge | shadow |
| A6 | 21–22, 26 | Canonical entity + JobHub consume-only authorised quantities checks | shadow / fail-closed |
| A7 | 28 | Four-project first-failing-authority report harness | diagnostic |
| A8 | 25, 29–30 | Only after owner-approved sealed appends + GPT3 eval | blocked until review |

Blocked without owner/original PDF or other lanes: STACKER host proof (5),
BIFOLD semantic release (7), door-height convention (12), pitched ceilings (20),
fresh 120-target V2 score (29–30).

## Authority boundaries that stay untouched

Frozen holdout truth, scorer, tolerances, source PDFs, 20 000 primitive cap,
2.5 pt snap, W10 takeoff flags, commercial extract / JobHub publishers until a
separate promotion review, and all GPT MAX / GPT1 / GPT2 producer modules except
explicit Cursor-owned integration/shadow seams.

## Benchmark observations that must not influence implementation

Documented two-project 8/51, full suite 120, “119 of 120”, STACKER 5.67 m²,
expected BOQ values, project names, and gold mappings are **post-producer
reporting only**. They must not enter thresholds, tests as oracles for producer
logic, or ranking.

## Release criterion for a Cursor development

A development counts only when it ships implementation (or justified abstention
harness), tests, signed-output retention evidence where applicable, a
`cursor/*` PR, and an explicit handoff naming the next lane owner. Diagnostics
alone are not a completed development unless they encode a reusable contract used
by a later stage.
