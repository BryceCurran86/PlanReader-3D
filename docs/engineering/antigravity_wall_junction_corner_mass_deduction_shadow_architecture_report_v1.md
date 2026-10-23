# Antigravity Wall Junction Corner Mass Deduction Authority Report (v1)

## Executive Summary
In 3D wall takeoff and structural modeling, intersecting perpendicular walls (L-junctions, T-junctions, cruciform/X-junctions) double-count the shared corner volume if each wall is modeled end-to-end. Without rigorous corner mass deduction, wall volume and surface area estimates are systematically oversized by the square of wall thickness at every corner.

This milestone (Item 66 / Workstream A Item 4 & 6) implements the producer-owned wall junction corner mass deduction shadow authority (`pb_source_wall_junction_corner_mass_deduction_shadow.py`).

## Core Architecture & Invariants

1. **Junction Classification (`JunctionKind`)**:
   - `L_JUNCTION_CORNER`: 90-degree corner meeting two wall endpoints.
   - `T_JUNCTION_ABUTMENT`: Secondary wall terminating perpendicular to a continuous through-wall.
   - `X_JUNCTION_CROSSING`: Four-way intersection.

2. **Disjoint Volume Partitioning**:
   - Continuous through-wall retains complete un-truncated mass through the junction.
   - Overlap area $A_{overlap} = T_{through} \times T_{abut}$ is deducted from the secondary abutting wall.
   - Deducted volume $V_{deducted} = A_{overlap} \times H_{wall}$.

3. **Obscured Finish Surface Deduction**:
   - Identifies the contact face obscured by the abutting wall butt-joint ($L_{obscured} = T_{abut}$).
   - Obscured finish area $Area_{obscured} = L_{obscured} \times H_{wall}$ is deducted from paint/plasterboard takeoff.

4. **Shadow Mode Invariants**:
   - Candidate status only (`status = CANDIDATE` / `CORROBORATED` internally).
   - Non-publishing: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Customer retention baseline preserved byte-for-byte.
