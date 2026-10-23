# GPT MAX — opening authority recovery: architecture review (2026-10-20)

**Status:** Review only. No code promotion, new FIRM quantity, customer-output mutation, or benchmark-score claim. This is the first deliverable mandated by `AGENTS.md`.

## Source compliance and inspected paths

Read from default branch: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, `pb_opening_host_frame_authority.py`, `tools/diag_gptmax_lot16_host_frame_gpt1_handoff.py`.

Exact observed function trace:

1. `OpeningHostFrameProducer` in `pb_opening_host_frame_authority.py` consumes producer-owned physical opening, structural host binding, and physical wall candidate authorities. It resolves source-space PDF-point wall frames; it **does not** resolve physical scale, vertical placement, commercial quantity, or count.
2. `OpeningHostFrameAuthority.resolve` is a selector-only published-identity lookup; a missing selector abstains.
3. `original_host_frame_dimension_report` in `tools/diag_gptmax_lot16_host_frame_gpt1_handoff.py` reads original PDF bytes, composes wall/opening and void authorities, and checks that source snapshots and signed customer retention do not mutate.
4. `assess_gpt1_opening_candidates` validates source root, canonical physical identity, host ancestry, whole-wall frame, two-axis figured area, width/height axis ownership, and filling kind. It emits **first_remaining_gate**, not a new signed quantity.

Boundary chain: original PDF source → physical opening existence → canonical opening identity → unique structural host → whole-wall frame → typed filling kind → figured dimensions → axis ownership → GPT1 firm measurement and signing → GPT3 independent reconciliation. Each stage must carry producer provenance; later stages cannot grant an earlier missing authority.

## Observed repository behavior

- The diagnostic asserts `measurement_published=False`, `customer_seal_granted=False`, and `opening_count_granted=False` for all handoff rows.
- The diagnostic's `new_gpt1_candidate_handoff` flag requires authenticated host, frame, type, dimensions and axis ordering, plus no previous quantity. It is a review queue only.
- Frame geometry is explicitly `pdf_point`, not metres.
- The 2026-10-16 accuracy index records the earlier source-backed Lot16 opening inventory as 21 physical opening records, 8 signed opening areas and 13 without quantity (6 missing host, 3 missing frame, 3 missing type, 1 with insufficient figured dimensions). These are **historical receipts**, not a new live replay or a basis for algorithmic tuning.
- A subsequent user-reported page-3 diagnostic claimed 12 of 12 host bindings corroborated. This report has **not** independently authenticated that output or established whether it is the same source/snapshot/universe as the historical 21, so it must not replace the baseline.

## Inferences to test, not established facts

- Opening recovery may now be gated more often by frames, kind, or dimension ownership than by host identity; only a fresh same-source full-scope replay with per-object receipts can establish this.
- A whole-wall frame can be geometrically valid yet insufficient to identify the opening filling or metric height.
- Earlier valid opening areas must not be duplicated if their wall, schedule, or label appears again on a sibling view.

## Proposed change sequence (separate PRs after architecture review)

1. **Receipt refresh, no behavioral change:** run exact original source `original_host_frame_dimension_report` with pinned source SHA and snapshot; preserve every per-opening `first_remaining_gate`; compare inventory completeness and previous signed rows. Attach artifact, not gold mappings, to tracker.
2. **Host-identity shadow recovery:** for cases with `structural_host_unavailable`, use producer-owned structural membership/equivalence; explicitly retain ambiguous candidates and fail closed. Test split/rotate/translate/insertion order, furniture look-alikes, near-parallel unrelated walls, and source-snapshot mismatch.
3. **Whole-wall frame shadow recovery:** for cases with `whole_wall_frame_unavailable`, prove positive continuity and explicit physical distinctness from aligned disconnected walls. No proximity tie-breaks.
4. **Door/window filling kind:** separately bind positive source glyph/leader/schedule evidence to a physical opening without inferring filling type from a gap or host.
5. **Dimension-axis/vertical evidence:** source-owned width and height evidence plus specific opening identity; do not borrow a door height from a datum or typical standard. Any user-approved exception must be an explicit separate authority record.
6. **Opening-count completeness:** reconcile deduplicated instances against a proven complete universe; no default count=1, no schedule-row-as-instance shortcut.
7. **GPT1 quantity handoff:** once the exact scope and all stage receipts pass, use existing firm measurement authority and seal; retain old quantity IDs, fingerprints and lineage unchanged.
8. **GPT3 score proof:** execute frozen V2 evaluator **after** source-closed quantities are sealed. Report matched targets, abstentions, regression checks and total coverage; do not change truth/tolerances.

## Predicted abstentions

- Missing or conflicting host membership → `structural_host_unavailable`.
- Unproven whole-wall extent or aligned unclassified structural fragments → `whole_wall_frame_unavailable`.
- A structural opening with no positive evidence of a door/window filling → `opening_filling_kind_unproven`.
- One figured dimension or non-owned label → `source_figured_dimension_pair_unproven`.
- Unproven dimension order/axes → `width_height_axis_authority_unproven`.
- Incomplete physical candidate universe → count abstains.
- Stale source SHA, revision, snapshot or decision scope → all dependent promotions abstain.

## Required proof matrix before any code promotion

Synthetic positives and look-alike negatives; two-host ambiguity and conflicting physical-equivalence records; geometric rotation/translation/scale metamorphism; segment splitting, input ordering and unrelated-content invariance; deterministic replay/stable IDs; no mutation; exact-source signed-output retention; default-off shadow mode; original-source full-scope receipt and independent authority review on exact commit.

## Unchanged boundaries

Do **not** edit `benchmarks/frozen_holdout/full_plan_v2/**`, `documents/sources/*.pdf`, `pb_planreader_pdf_extractor.py`, `pb_planreader_jobhub_publish_contract.py`, live commercial publishers, scorer, tolerances, 20,000 primitive safety cap, snap tolerance, or opening count/height defaults. No global `min_area` promotion.

## Release criterion

A task completes only when a new source-owned gate passes with receipts **and** its downstream consumer sees that same physical identity, while historical signed output is unchanged except for independently approved appended quantities. `99%` is a post-evaluation target, never a code input. Full-suite 99% is not established by this architecture review.
