# Architecture Report: Source Expansion Joint Floor & Wall Architectural Cover Plate Shadow Authority (v1)

## Executive Summary
Large building envelopes and multi-wing floor plates incorporate continuous structural expansion joints (50mm–150mm gap) to absorb thermal movement, concrete shrinkage, and seismic sway. Architectural interior and exterior finishes must bridge these discontinuities with engineered joint cover assemblies ensuring trip-free pedestrian traffic, fire containment, and water tightness.

This module introduces `SourceExpansionJointCoverShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for architectural floor cover plates, wall/ceiling cover systems, sub-joint EPDM moisture gutters, and multi-hour fire barrier blankets directly from architectural finish plans and detail drawings.

## Domain Model & Joint Cover Anatomy
1. **Cover System Type (`CoverSystemType`)**:
   - `FLUSH_ELASTOMERIC`: Extruded aluminium side frames with flush elastomeric Santoprene seals (commercial pedestrian traffic).
   - `ALL_METAL_HEAVY_DUTY`: Heavy-duty articulated aluminium or stainless steel plate system for vehicular, service cart, or heavy equipment loading.
   - `SURFACE_MOUNTED_PLATE`: Beveled metal cover plate mechanically fastened on one side with slot anchors on the floating side.
   - `VERTICAL_WALL_COVER`: Snap-fit architectural wall cover profile bridging partition gaps.
2. **Sub-Joint Moisture Barrier (`has_moisture_barrier`)**:
   - Continuous flexible EPDM gutter membrane suspended below exterior or wet-area joints with drainage droppers.
3. **Fire Barrier Blanket (`has_fire_barrier`, `fire_rating_hours`)**:
   - Tested ceramic fiber / mineral wool blanket wrapped in stainless steel mesh bridging the structural gap (e.g. 2-hr or 3-hr fire resistance).

## Mathematical Formulations
- **Linear Joint Cover Run (\(L_{cover}\))**:
  \[
  L_{cover} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Fire Barrier Blanket Linear Run (\(L_{fire\_barrier}\))**:
  \[
  L_{fire\_barrier} = \sum_{i \in \text{FireRated}} L_{cover, i}
  \]
- **EPDM Moisture Gutter Linear Run (\(L_{moisture}\))**:
  \[
  L_{moisture} = \sum_{i \in \text{MoistureGutter}} L_{cover, i}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for joint centerline endpoints and partition intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
