# Architecture Report: Source HVAC Ductwork Penetration & Fire Damper Sleeve Shadow Authority (v1)

## Executive Summary
Mechanical HVAC air distribution ductwork frequently crosses fire-rated building compartments, acoustic barriers, and structural floor slabs. When a duct breaches a rated wall or slab, life safety codes (e.g. AS 1668.1, BCA/NCC Part C3) mandate motorized fire/smoke damper sleeves, retaining mounting flanges, breakaway expansion connections, and annular firestop sealant packing.

This module introduces `SourceHVACPenetrationDamperShadowAuthority`, enabling authoritative shadow-mode parsing, validation, and multi-component takeoff of duct penetrations, damper sleeves, retaining flange angles, and firestop packing volumes directly from mechanical ductwork layouts and fire partition drawings.

## Domain Model & Penetration Anatomy
1. **Duct Penetration (`FireDamperSpec`)**:
   - Rectangular (\(W \times H\)) or circular (\(\varnothing D\)) sheet metal duct passing through a structural boundary.
2. **Penetrated Element (`PenetratedElementKind`)**:
   - `WALL_PARTITION`: Vertical fire-rated drywall, core-filled masonry, or concrete wall.
   - `FLOOR_SLAB`: Horizontal suspended concrete floor slab.
3. **Damper Sleeve**:
   - Heavy-gauge steel casing (1.2mm–1.6mm) housing the damper blades, extending past both partition faces:
     \[
     L_{sleeve} = t_{element} + 2 \times \text{extension\_mm} \quad (\text{typically } 2 \times 150\text{mm})
     \]
4. **Retaining Flange Mounting Angles (`L_{flange}`)**:
   - Continuous steel angles (40x40mm) framing the sleeve on both sides of the wall:
     \[
     L_{flange} = 2 \times \text{Perimeter}_{sleeve}
     \]
5. **Annular Firestop Packing Void**:
   - 25mm to 50mm clearance gap around the sleeve packed with high-density mineral wool and intumescent firestop mortar.

## Mathematical Formulations
- **Rough Wall/Slab Opening Area (\(A_{opening}\))**:
  For rectangular duct with annular gap \(g\):
  \[
  A_{opening} = \left(\frac{W_{mm} + 2g}{1000}\right) \times \left(\frac{H_{mm} + 2g}{1000}\right)
  \]
- **Duct Cross-Sectional Area (\(A_{duct}\))**:
  \[
  A_{duct} = \left(\frac{W_{mm}}{1000}\right) \times \left(\frac{H_{mm}}{1000}\right)
  \]
- **Annular Firestop Packing Volume (\(V_{firestop}\))**:
  \[
  V_{firestop} = (A_{opening} - A_{duct}) \times \left(\frac{t_{element, mm}}{1000}\right)
  \]
- **Retaining Flange Steel Angle Linear Length (\(L_{flange}\))**:
  \[
  L_{flange} = 2 \times 2 \times \left(\frac{W_{mm} + H_{mm}}{1000}\right) = 4 \times \left(\frac{W_{mm} + H_{mm}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for duct centerlines and partition intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
