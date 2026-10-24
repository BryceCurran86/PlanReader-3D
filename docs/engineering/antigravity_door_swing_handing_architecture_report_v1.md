# Architecture Report: Source Door Swing Direction & Handing Shadow Authority (v1)

## Executive Summary
In architectural plans, door openings convey operational semantics through thin circular arc strokes representing door leaf swing. Door swing direction determines:
1. Architectural handing (LH, RH, LHR, RHR) essential for door hardware schedules and ironmongery specifications.
2. Direction of travel (inward vs outward) for egress compliance and accessibility code.
3. Swept floor clearance envelope ($\frac{\pi r^2}{4}$) which cannot be obstructed by walls, fixtures, or conflicting door swings.

This authority correlates door leaf segments with radial swing arcs to resolve exact hinge/latch coordinates, swing angle, handing, and swept clearance area in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 8 / Workstream B Item 14:** Doorway geometry, swing orientation, and opening hardware.

## Handing Classification & Clearance Model
1. **Door Handing Types:**
   - `LEFT_HAND_INWARD`: Hinge on left, swings into room interior.
   - `RIGHT_HAND_INWARD`: Hinge on right, swings into room interior.
   - `LEFT_HAND_OUTWARD`: Hinge on left, swings outward into egress corridor.
   - `RIGHT_HAND_OUTWARD`: Hinge on right, swings outward into egress corridor.
   - `DOUBLE_EGRESS`: Paired leaves swinging in opposite or identical directions.
   - `SLIDING_OR_CAVITY`: Sliding pocket or surface door without radial arc.

2. **Swept Area Calculation:**
   - For 90-degree radial swings: $A_{swept} = \frac{\pi \cdot r^2}{4}$, where $r$ is the leaf length.

3. **Invariants & Safety:**
   - Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
   - `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Global 2.5 pt snap tolerance.
   - Preserves byte-for-byte customer retention.
