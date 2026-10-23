# Architecture Report: Source Wall Material Hatch Pattern Semantic Binding Shadow Authority (v1)

## Executive Summary
Architectural plan drawings differentiate wall construction materials using standard vector hatch patterns within enclosed wall geometries. Without hatch pattern parsing, downstream takeoff and structural synthesis treat all walls identically, failing to distinguish between loadbearing reinforced concrete cores, brickwork masonry, CMU blockwork, lightweight drywall stud partitions, and insulated sandwich panels.

This authority binds vector hatch pattern geometry inside wall polygons to semantic wall materials with confidence scoring, while remaining strictly in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 5:** Wall material specification, physical hatching, and construction type.

## Hatch Classification & Material Mapping
1. `SOLID_FILL`: Solid fill polygon -> `STRUCTURAL_CONCRETE` (is_structural=True, high strength).
2. `DIAGONAL_SINGLE`: 45-degree diagonal lines -> `BRICK_MASONRY` (is_structural=True).
3. `CROSS_HATCH_DIAMOND`: Cross-hatch diamond pattern -> `CONCRETE_MASONRY_UNIT` (is_structural=True).
4. `STIPPLE_DOTS`: Stipple dot distribution -> `CAST_IN_PLACE_CONCRETE` (is_structural=True).
5. `INSULATION_BATT_OR_ZIGZAG`: Zig-zag or sine wave -> `INSULATED_SANDWICH_PANEL` (e.g. freezer/coolroom panels).
6. `EMPTY_OR_UNHATCHED`: No interior strokes -> `LIGHTWEIGHT_STUD_DRYWALL` (non-structural or unconfirmed).

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
