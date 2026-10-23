# GPT1 → GPT MAX: measurement authority and signed quantity recovery (2026-10-20)

**Stage:** Required architecture review before changes to production behavior (AGENTS.md). **No FIRM quantity or new score claimed.**

## Compliance and real functions read

Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, `tools/diag_gptmax_lot16_host_frame_gpt1_handoff.py`, `pb_opening_host_frame_authority.py`, `pb_measurement_input_authority.py`, `pb_figured_dimension_authority.py`, `pb_quantity_takeoff_adapter.py`, `pb_source_closed_run_export.py`.

Observed call/authority path:

1. `original_host_frame_dimension_report` composes live source-owned opening/host/frame authority and verifies snapshot + signed-output retention before emitting diagnostic candidates.
2. `assess_gpt1_opening_candidates` checks original physical opening ID, host ancestry, frame source-space geometry, figured dimension pair, axis order, opening kind and first failing gate. Its `new_gpt1_candidate_handoff` is **not** a signed quantity.
3. `OpeningHostFrameAuthority.resolve` selects source-space frame evidence; `pdf_point` origin/axis/wall length does not establish metric dimensions or vertical height.
4. `resolve_linear_measurement_input` in `pb_measurement_input_authority.py` is an existing trusted source/revision/page/viewport/entity-bound seam; only FIRM authority returns a length.
5. `resolve_measurement_authority` and `parse_figured_dimension_mm` in `pb_figured_dimension_authority.py` parse/validate figured measurements. Text interpretation alone does not bind a printed number to a particular door height, especially when the number is a datum.
6. `quantity_status_not_publishable` in `pb_quantity_takeoff_adapter.py` fails closed for non-firm/non-corroborated states. `pb_source_closed_run_export._lineage_reasons` rejects stale/superseded, conflicting source traces and non-publishable shadow metadata.

## Observed vs inference vs proposed change

**Observed:** The Lot16 2026-10-16 owner-source ledger reports 21 physical openings, eight signed areas, and 13 unsigned: six host-blocked, three frame-blocked, three kind-blocked, one insufficient figured pair. This is an archived diagnostic baseline, not an independently rerun score. The same index reports missing source-owned door-height authority on inspected sheets. The historical source-independent signed areas must not be recreated or rekeyed.

**Inference:** A newer host-binding pass may improve host coverage, but that alone cannot satisfy frame continuity, filling kind, width/height axis ownership or vertical height. A wall-host improvement can produce zero new firm area quantities.

**Proposed staged engineering:**

1. Reproduce exact original Lot16 full-scope diagnostics using the immutable PDF; retain opening identity, source SHA, revision, snapshot and first failing gate for **all** original objects. Verify changed host counts are on the same scope, not a subset.
2. Consume only source-owned, same-snapshot MAX host+whole-wall frame evidence; fail closed on stale identity, missing physical type or unproven frame.
3. Source-analyse figured dimension evidence with witness/leader and exact physical opening ownership; distinguish width vs height without positional nearest/first defaults. Use `resolve_linear_measurement_input` and the existing figured-dimension authority.
4. For any single width without source-backed height, keep opening_area **ABSTAIN**. Do not synthesize 2100mm, 2040mm or other conventional heights. Any explicitly user-approved exception must be a separate scoped, recorded authority decision.
5. Build a **shadow-only** GPT1 readiness report grouping the **first** remaining gate per physical ID; never count a physical opening solely because a schedule row or host fragment exists.
6. After source+unit+quantity gate review, construct genuine FIRM quantity through existing quantity contract, produce independently signed rows, and append without mutating prior eight Lot16 sealed rows. GPT3 runs the frozen evaluator separately.
7. Parallel Maryborough: consume GPT2-authenticated physical room floor faces and FT2/FT3 occurrences; measure floor finish to **internal wall face**. Floor covering stops at door/entrance finish transition and never passes under a wall. Ceiling IPF1/grid/CL03/external soffits require exact zones, not text-mark guesses.
8. Lot16 floor and raked ceilings: prove room geometry and exact pitch/plane before any sloped area; wall faces require verified height and net openings separately.

## Predicted abstentions

- Host binding or frame scope stale/incomplete → no metric measurement.
- Door/window filling kind not source-owned → no typed opening quantity.
- One figured dimension only → no area.
- Two dimensions but unproven axis identity → no firm width/height.
- Generic note or datum without physical opening ownership → no inferred door height.
- Ambiguous FT2/FT3 plan occurrence → no floor-finish publication.
- Room boundary open or finish zone unclosed → no area.
- Incomplete instance universe → no opening count.

## Proof requirements

Synthetic positive, conflicting/twin opening, symbol/furniture look-alike negative; separate width-only and height-datum-only negatives; input order/rotation/translation/scale and segment split invariance; sibling viewport expansion; stale SHA/snapshot; stable quantity and identity receipts; commercial unchanged in shadow; Lot16 signed eight rows byte-identical for non-promoting PRs; Maryborough existing signed floor rows retained; frozen benchmark checks unchanged.

## Do not touch

`benchmarks/frozen_holdout/full_plan_v2/**`, `documents/sources/*.pdf`, `pb_planreader_pdf_extractor.py`, customer publish contract, scorer/tolerances, original eight sealed Lot16 quantity bodies, safety primitive cap (20,000), 2.5-pt snap behavior, default counts/heights. No new production quantity until independent authority review.

## Acceptance milestone

For **each** genuinely new signed quantity: authenticated source-owner evidence for the physical entity and measurements → existing trusted authority seam → unchanged historical signed identities → verified GPT3 post-seal frozen match. A 99% target is not evidence that missing measurements exist, and may require source-approved abstention where drawings do not specify dimensions.
