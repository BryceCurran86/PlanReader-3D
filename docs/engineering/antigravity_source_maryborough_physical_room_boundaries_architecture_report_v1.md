# Architecture Report: Producer-Owned Maryborough Physical Room Boundary Shadow Authority (Items 11 & 13)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Maryborough Physical Room Boundary Shadow Authority** (`pb_source_maryborough_physical_room_boundary_shadow.py`), resolving Workstream B, Item 11 ("Complete OFFICE, FREEZER, WASH UP and FOOD PREP physical boundaries") and Item 13 ("Complete LAUNDRY, AIRLOCK, PWD, M-AMB and F-AMB") of the Autonomous Core Accuracy Engineering Mission.

The primary blockers addressed are:
1. **Unresolved Room Boundaries at Door Openings:** In prior pipeline stages, rooms such as OFFICE, FREEZER, WASH UP, FOOD PREP, LAUNDRY, AIRLOCK, PWD, M-AMB, and F-AMB remained in `abstained_faces` because doorway opening spans lack containing structural wall candidates. The room polygon's door edge was treated as a missing wall defect (`EDGE_OWNERSHIP_NONE`).
2. **Missing Floor Finish Transition Lineage:** Construction rules require floor finishes (e.g. FT2 tiles in wet areas, FT3 vinyl in food areas, carpet in office) to terminate at internal wall faces, with finish transitions occurring strictly across the physical doorway threshold line.
3. **Producer-Owned Closure and Metric Calibration:** This module establishes an immutable producer/authority contract that validates 2D closed polygon boundaries, associates door opening chords within standard snap tolerance ($\le 2.5$ pt), attributes floor finish codes, and derives scale-calibrated metric areas ($m^2$) and perimeters ($lm$) without inventing artificial dividing partitions.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceMaryboroughPhysicalRoomBoundaryProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceMaryboroughPhysicalRoomBoundaryAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Room Boundary Geometric Gates
- **Target Room Coverage:**
  - Item 11 targets: `OFFICE`, `FREEZER`, `WASH_UP`, `FOOD_PREP`.
  - Item 13 targets: `LAUNDRY`, `AIRLOCK`, `PWD`, `M_AMB`, `F_AMB`.
  - Robust name normalization converts variations (e.g. `M-AMB` $\to$ `M_AMB`, `WASH UP` $\to$ `WASH_UP`).
- **Doorway Opening Verification:**
  - Rooms connect to circulation networks via authenticated doorway transitions (e.g. D07 for Office, D10 for Laundry, D11 for F-AMB, D12 for M-AMB, D13 for PWD, D08/D09 for Airlock).
  - Door opening chords must sit on or within $\le 2.5$ pt of the room polygon boundary. Discontinuous or displaced opening chords trigger `ROOM_WALL_DEFECT_REMAINS` and cause immediate failure (`ABSTAINED`).
  - Completely enclosed rooms without door candidates are flagged with `ROOM_DOOR_TRANSITION_MISSING`.
- **Wall Face Presence & 2D Closed Polygon Gate:**
  - Must cite verified internal wall face segments (`wall_face_segment_ids`).
  - Validates polygon closure, orientation, and non-self-intersection. Degenerate or collinear points fail with `ROOM_INVALID_GEOMETRY` and `ROOM_BOUNDARY_NOT_CLOSED`.
- **Scale Calibration:**
  - Calibrated scale converts pixel coordinates to metric dimensions:
    $$\text{area\_m2} = \frac{\text{area\_pt2}}{\text{scale\_px\_per\_m}^2}$$
  - OGC WKB polygon geometry is exported for spatial verification.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
