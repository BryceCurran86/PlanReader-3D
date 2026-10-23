# Batch43 — exact geometry identity (not digit-tail)

## Observed

- Segment-parent lines (8/unhosted) vs usable W4 **centerline edges**: **0 exact matches** on all 6 Lot16 unhosted openings → `exact_geometry_identity_unavailable`.
- Digit-tail collisions (batch42) remain against `raster_segment:` IDs but do **not** coincide with exact centerline geometry identity.
- GPT MAX #3412 fragment-ownership fields are **not** present on this Cursor branch (`gptmax_3412_fragment_field_present_any=false`); Cursor will not cherry-pick as host.
- Kind-unproven ledger: 7 openings; single-figured 870 mm ×8 (no invent height).

## Inference (not authority)

- Opening-primitive segment geometry is not the same object as W4 wall centerline edges under current producers.
- Host still requires producer-owned identity (visible-line assembler and/or authenticated primitive map), not digit-tail or nearest geometry.

## Proposed (shadow only)

- Keep exact-geometry census fail-closed.
- Unique-wall exact match would still be `…_review_only` (no host) if it ever appears.
- Multi-wall exact match aborts (`…_ambiguous_multi_wall`).

## Benchmark that must not drive algorithms

- Expected BOQ / V2 scores; signed area values.
