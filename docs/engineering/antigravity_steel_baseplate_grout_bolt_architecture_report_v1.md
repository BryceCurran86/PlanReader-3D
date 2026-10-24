# Architecture Report: Source Structural Steel Baseplate, Grout Bed & Anchor Bolt Assembly Shadow Authority (v1)

## Executive Summary
In structural steel construction, column loads transfer to reinforced concrete footings and pedestal piers through baseplate connection assemblies. Structural drawings and connection schedules govern baseplate dimensions, anchor bolt (HD bolt) diameters and embedment depths, and high-strength non-shrink cementitious grout packing beds.

This module introduces `SourceSteelBaseplateGroutBoltShadowAuthority`, enabling authoritative shadow-mode parsing, validation, and multi-component material takeoff of baseplates, cast-in holding down bolts, and dry-pack grout beds directly from structural marking plans and connection schedules.

## Domain Model & Connection Anatomy
1. **Steel Baseplate (`SteelBaseplateSpec`)**:
   - Heavy hot-rolled steel plate (e.g., Grade 250/350 steel) welded to the column base.
   - Sized by plan width, length, and plate thickness (typically 16mm to 40mm).
   - Steel density: \(7850 \text{ kg/m}^3\).
2. **Holding Down (HD) Anchor Bolts**:
   - High-tensile threaded rods (e.g., 4 x M24 or 6 x M30 Grade 8.8) cast directly into concrete footings.
   - Specified by bolt diameter, embedment depth, and cage pattern pitch.
3. **Non-Shrink Cementitious Grout Bed**:
   - High-early-strength non-shrink grout packed between the rough concrete footing surface and the steel baseplate underside.
   - Bed thickness typically ranges from 25mm to 50mm, projecting ~50mm beyond the baseplate perimeter.

## Mathematical Formulations
- **Baseplate Steel Mass (\(M_{plate}\))**:
  \[
  M_{plate} = \left(\frac{W_{mm}}{1000} \times \frac{L_{mm}}{1000} \times \frac{t_{plate, mm}}{1000}\right) \times 7850 \text{ kg/m}^3
  \]
- **Anchor Bolt Steel Rod Linear Length (\(L_{bolts}\))**:
  \[
  L_{bolts} = N_{bolts} \times \left(\frac{L_{embed, mm} + t_{plate, mm} + t_{grout, mm} + 75\text{mm}}{1000}\right)
  \]
- **Non-Shrink Grout Volume (\(V_{grout}\))**:
  With standard 50mm perimeter grout shoulder chamfer:
  \[
  V_{grout} = \left(\frac{W_{mm} + 100}{1000}\right) \times \left(\frac{L_{mm} + 100}{1000}\right) \times \left(\frac{t_{grout, mm}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for column grid center snapping.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
