# Architecture Report: Source Structural Retaining Wall & Subsoil Drainage Agrégat Shadow Authority (v1)

## Executive Summary
Retaining walls resist lateral earth and hydrostatic pressure across site level transitions and subterranean basement perimeters. Beyond the structural stem and continuous footing (toe/heel), retaining systems require behind-wall hydrostatic relief consisting of subsoil perforated agricultural pipe (ag-pipe), geofabric-wrapped aggregate backfill drainage aggregate, and tanking waterproofing membranes.

This module introduces `SourceRetainingWallDrainageShadowAuthority`, providing an authoritative shadow-mode framework for parsing, validating, and quantifying retaining wall assemblies, subsoil drainage, and earth-face waterproofing directly from structural and civil drawings.

## Domain Model & Assembly Anatomy
1. **Wall Stem (`RetainingWallSpec`)**:
   - Vertical structural retaining element (reinforced concrete cantilever, core-filled concrete blockwork, or gravity mass).
   - Specified by stem thickness and retained earth height.
2. **Continuous Footing**:
   - Spread footing supporting the stem with front toe projection and rear heel projection to resist overturning and sliding.
3. **Subsoil Agricultural Drainage Pipe (`ag_pipe_diameter_mm`)**:
   - Slotted/perforated PVC/corrugated pipe laid at the base of the retained earth face behind the footing heel to carry away seepage water.
4. **Aggregate Drainage Layer (`agg_backfill_width_mm`)**:
   - Free-draining granular crushed aggregate (typically 200mm-300mm wide envelope) placed against the rear face.
5. **Tanking Waterproofing Membrane**:
   - Liquid or sheet applied waterproof tanking across the earth-retaining vertical face to prevent damp transmission.

## Mathematical Formulations
- **Linear Retaining Wall Length (\(L_{wall}\))**:
  \[
  L_{wall} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Stem Concrete Volume (\(V_{stem}\))**:
  \[
  V_{stem} = \sum_{i} L_{wall, i} \times \left(\frac{t_{stem, i}}{1000}\right) \times \left(\frac{H_{stem, i}}{1000}\right)
  \]
- **Footing Concrete Volume (\(V_{footing}\))**:
  \[
  V_{footing} = \sum_{i} L_{wall, i} \times \left(\frac{W_{footing, i}}{1000}\right) \times \left(\frac{D_{footing, i}}{1000}\right)
  \]
- **Drainage Aggregate Volume (\(V_{agg}\))**:
  \[
  V_{agg} = \sum_{i} L_{wall, i} \times \left(\frac{W_{agg, i}}{1000}\right) \times \left(\frac{H_{agg, i}}{1000}\right)
  \]
- **Earth Face Tanking Area (\(A_{tanking}\))**:
  \[
  A_{tanking} = \sum_{i} L_{wall, i} \times \left(\frac{H_{stem, i}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for adjacent polyline vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
