# Antigravity Multi-Level Floor Alignment and Vertical Void Shadow Authority Report (v1)

## Executive Summary
Multi-story and split-level drawings (stairwells, double-height voids, mezzanines, vertical service shafts/risers) fail when upper-level room footprints clash with lower-level ceiling planes or when stair voids are treated as solid floors, causing false floor takeoffs or missing vertical envelope connections.

This milestone (Item 63 / Workstream A Item 10 & Workstream C Item 27) implements the producer-owned multi-level floor alignment and vertical void shadow authority (`pb_source_multilevel_floor_vertical_void_shadow.py`).

## Core Architecture & Invariants

1. **Physical Void Classification (`VoidKind`)**:
   - `STAIRWELL`: Stairway penetrations spanning between levels.
   - `DOUBLE_HEIGHT_VOID`: Open mezzanine and double-height architectural voids.
   - `SERVICE_RISER`: Vertical mechanical, electrical, and plumbing risers.
   - `LIGHTWELL`: External or internal light penetration shafts.
   - `ESCALATOR`: Moving stair penetrations.

2. **Geometric Verification**:
   - Strict polygon boundary validation: fails closed on degenerate polygons ($N < 3$) and self-intersecting geometries (bowtie loops).
   - Scale-calibrated metric area ($m^2$) and perimeter ($m$).
   - Physical minimum area thresholds ($0.10 m^2$ for risers, $0.50 m^2$ for stairwells/voids) to reject noise artifacts.

3. **Multi-Level Floor Area Deduction**:
   - Computes net floor area: $\text{Area}_{net} = \text{Area}_{gross} - \sum \text{Area}_{void}$.
   - Deducts only corroborated vertical voids.
   - Maintains exact lineage with `subtracted_void_ids`.

4. **Shadow Mode Invariants**:
   - Candidate status only (`status = CANDIDATE` / `CORROBORATED` internally).
   - Strictly non-publishing: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Customer retention baseline preserved byte-for-byte.
