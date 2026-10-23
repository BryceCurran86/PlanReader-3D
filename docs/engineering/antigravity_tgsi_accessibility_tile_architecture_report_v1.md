# Architecture Report: Source Tactile Ground Surface Indicator (TGSI) Accessibility Hazard & Directional Warning Tile Shadow Authority (v1)

## Executive Summary
Statutory accessibility standards (e.g. AS/NZS 1428.4.1, ADA Standards Section 705, IBC Section 1109) mandate the installation of Tactile Ground Surface Indicators (TGSIs) to alert blind or vision-impaired pedestrians of hazards (stair flights, ramps, escalators, pedestrian road crossings) or provide directional wayfinding across public spaces. Architectural floor finish plans schedule tactile zones detailing indicator profile (hazard warning truncated domes vs directional raised bars), physical format (individual drilled studs vs surface-mounted integrated tiles), depth (600mm deep zone across travel path), and mandatory 300mm setback from stair nosings.

This module introduces `SourceTGSIAccessibilityTileShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for tactile ground indicator pads, individual stud counts, tile module counts, and square-meter takeoff directly from architectural floor plans and detail sections.

## Domain Model & TGSI Anatomy
1. **Indicator Profile (`TGSIType`)**:
   - `HAZARD_WARNING`: Truncated cones (studs) indicating an approaching drop-off or change of level.
   - `DIRECTIONAL_LEADING`: Raised directional bars with flat tops guiding safe transit routes.
2. **Material & Format (`TGSIFormat`)**:
   - `INDIVIDUAL_STUDS`: Discrete stainless steel 316, solid brass, or polyurethane studs drilled into floor finishes (400 studs/m² nominal standard grid).
   - `INTEGRATED_TILE`: Pre-cast porcelain, ceramic, composite, or stainless steel tiles (standard 300mm × 300mm or 300mm × 600mm).
   - `PEEL_AND_STICK_MAT`: Surface-applied polyurethane matting.
3. **Location Context (`TGSILocationContext`)**:
   - `STAIR_TOP`: 600mm deep pad setback 300mm from top nosing.
   - `STAIR_BOTTOM`: 600mm deep pad setback 300mm from bottom riser.
   - `RAMP_TOP_BOTTOM`: 600mm deep pad at ramp thresholds.
   - `ESCALATOR_APPROACH`: 600mm deep warning band across boarding line.
   - `PEDESTRIAN_CROSSING`: Curb ramp truncated dome tactile zone.

## Mathematical Formulations
- **Tactile Surface Area (\(A_{tgsi}\))**:
  \[
  A_{tgsi} = \sum_{i} \text{width}_i \cdot \text{depth}_i
  \]
  where width and depth are in meters (or calculated from the 2D bounding polygon).
- **Individual Stud Takeoff (\(N_{studs}\))**:
  \[
  N_{studs} = \sum_{i \in \text{INDIVIDUAL\_STUDS}} \text{round}(A_{tgsi, i} \cdot 400)
  \]
  based on the standard 50mm c/c orthogonal array yielding 400 studs per square meter.
- **Tile Module Units (\(N_{tiles}\))**:
  \[
  N_{tiles} = \sum_{j \in \text{INTEGRATED\_TILE}} \text{ceil}\left(\frac{A_{tgsi, j}}{0.09}\right)
  \]
  assuming standard 300mm × 300mm (0.09 m²) tile modules.

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for tactile zone boundary polygons and anchor points.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
