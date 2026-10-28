# GPT1: exact original room identity at floor-finish customer location (2026-10-29)

## Observed production path and first failing gate

Read current main `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, the accuracy-lever index and CI, then traced the real `CrossViewFloorFinishProducer` FIRM `floor_finish_area` quantity through `pb_live_floor_finish_area_source_closed_export.build_live_floor_finish_area_source_traces`, `pb_live_floor_finish_customer_projection.project_live_floor_finish_customer_rows`, `pb_quantity_takeoff_adapter.quantities_to_takeoff_output_rows`, `pb_source_closed_run_export.seal_source_closed_run` and `pb_customer_output_verification.verify_sealed_customer_output`. The unchanged frozen Full Plan V2 evaluator is downstream of sealed customer output.

The source trace builder maps the canonical floor's `room_entity_id` through `_clean()` into a canonical entity address when no separate canonical-room inventory is supplied. The customer projector independently maps that same field through `_clean()` into the commercial `location` string. A replayed canonical floor can therefore present a non-native, blank, padded or string-coerced source room address while retaining an otherwise FIRM floor-finish quantity. This is a missing exact original source-identity gate at the **real customer row**, not a reason to create a new area.

## Inference

The quantity's metric, original material mark and source trace can remain unchanged while its commercial room location is absent or coerced. This could mislocate a real floor-finish customer row even when the numerical area remains unchanged. It does not prove any original Maryborough room, FT2/FT3 mark or ceiling quantity.

## Proposed narrow implementation

At the existing FIRM floor-finish customer projection boundary, require the selected canonical floor's room entity ID to be an exact native nonempty, unpadded `str`. Use the unchanged original value for `location`; never derive a room label, normalize an alias or invent an owner. Reject invalid source identity with the existing `SourceClosedRunConflictError`. Preserve valid FIRM rows, legitimately abstained source siblings and existing sealed/customer parity.

Adversarial real-projector tests cover missing, blank, padded and coerced source room identities plus a valid positive and source non-mutation. This is negative-only integrity, not a new source-verified FIRM quantity or official V2 match.

## Files and authority kept untouched

No changes to GPT2 original room, FT2/FT3, doorway or RCP producers; GPT MAX/Claude hosts or glazing; GPT3 signing/scoring; GPT1 existing floor source exporter or source/quantity issuer; private original PDFs, source hashes/tokens, frozen V2 truth/evaluator, previously signed Lot16 customer bodies, 20,000 primitive limit or 2.5pt snap. Original-source replay and signed/customer preservation remain mandatory before any merge.
