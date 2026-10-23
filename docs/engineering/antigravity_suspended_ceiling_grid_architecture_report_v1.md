# Architecture Report: Source Suspended Ceiling Grid System & Hanger Wire Grid Shadow Authority (v1)

## Executive Summary
Commercial office spaces, education facilities, and healthcare suites predominantly utilize modular two-way suspended acoustic tile ceiling systems installed beneath suspended concrete or steel structures. Reflected Ceiling Plans (RCP) and interior details delineate grid modular dimensions, ceiling finished levels, and plenum voids.

This module introduces `SourceSuspendedCeilingGridShadowAuthority`, providing an authoritative shadow-mode framework for extracting ceiling boundary polygons, modular grid configurations, suspension hanger wire grids, and structural perimeter wall angles directly from 2D vector RCP drawings.

## Domain Model & Grid Anatomy
1. **Ceiling Grid Module (`CeilingGridModule`)**:
   - `GRID_1200X600`: Standard commercial module (1200mm x 600mm tiles).
   - `GRID_600X600`: Fine-square institutional module (600mm x 600mm tiles).
   - `GRID_1200X300`: Linear acoustic metal plank module.
2. **Main Runners (`L_{main}`)**:
   - Primary slotted T-bars suspended parallel to each other at 1200mm centers.
3. **Cross Tees (`L_{cross}`)**:
   - Interlocking transverse T-bars connecting main runners at 600mm increments.
4. **Perimeter Wall Angle Trim (`L_{perimeter}`)**:
   - Extruded aluminium or steel L-angle fixed continuously around the room perimeter walls.
5. **Suspension Hanger Wires (`L_{wire}`)**:
   - Vertical galvanized wires anchored to the structural soffit above, supporting main runners at max 1200mm x 1200mm spacing.
   - Wire length equals ceiling plenum depth (slab soffit level minus finished ceiling level).

## Mathematical Formulations
- **Net Ceiling Soffit Area (\(A_{ceil}\))**:
  \[
  A_{ceil} = \text{PolygonArea}(\text{boundary})
  \]
- **Main Runner Linear Run (\(L_{main}\))**:
  \[
  L_{main} = \frac{A_{ceil}}{1.20}
  \]
- **Cross Tee Linear Run (\(L_{cross}\))**:
  For 1200x600 module: \(L_{cross} = \frac{A_{ceil}}{0.60}\).
- **Hanger Wire Count (\(N_{hangers}\))**:
  \[
  N_{hangers} = \left\lceil \frac{A_{ceil}}{1.20 \times 1.20} \right\rceil
  \]
- **Total Hanger Wire Length (\(L_{wire}\))**:
  \[
  L_{wire} = N_{hangers} \times \left(\frac{\text{plenum\_depth\_mm}}{1000}\right)
  \]
- **Estimated Tile Count (\(N_{tiles}\))**:
  \[
  N_{tiles} = \left\lceil \frac{A_{ceil}}{W_{mod} \times L_{mod}} \right\rceil
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for room boundary vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
