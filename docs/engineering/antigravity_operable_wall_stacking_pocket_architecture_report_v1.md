# Architecture Report: Source Architectural Operable Acoustic Movable Wall Track & Stacking Pocket Shadow Authority (v1)

## Executive Summary
Flexible corporate, civic, and educational interiors frequently specify high-performance operable movable wall systems that subdivide large multi-purpose halls into separate acoustic zones. Operable walls are suspended from overhead extruded aluminium or structural steel tracks anchored to secondary ceiling structural framing (ensuring threshold-free floors) and retract into enclosed stacking pockets or remote parking bays when open. Panels feature retractable mechanical pressure seals to achieve rated acoustic performance (Rw 45 to 55 dB).
This report establishes the candidate shadow authority for parsing and extracting operable wall track centerlines, stacking pocket enclosures, acoustic ratings, and clearance geometry from architectural plans and details.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `OPERABLE WALL`, `ACOUSTIC OPERABLE WALL`, `MOVABLE PARTITION`, `OPERABLE PARTITION`, `STACKING POCKET`, `OVERHEAD TRACK`, `STACKING BAY`.
2. **Key Physical Parameters**:
   - `partition_type`: `ACOUSTIC_OPERABLE_WALL`, `GLASS_MOVABLE_WALL`, `ACCORDION_PARTITION`.
   - `acoustic_rating_rw`: Sound reduction index (e.g. `Rw 45`, `Rw 50`, `Rw 55`, `STC 50`).
   - `height_mm`: Operable panel height (e.g. `2700MM`, `3000MM`, `3600MM`).
   - `stacking_type`: `PARALLEL_STACKING_POCKET`, `PERPENDICULAR_STACKING`, `REMOTE_STACKING_BAY`.
   - `seal_type`: `EXPANDING_MECHANICAL_SEAL`, `SWEEP_SEALS`, `AUTOMATIC_PRESSURE_SEAL`.
3. **Geometric Snapping & Polyline Representation**:
   - Track centerlines and stacking pocket boundary lines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total track or perimeter length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
