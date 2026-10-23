# Architecture Report: Source Structural Steel Bracing Member & Gusset Plate Connection Shadow Authority (v1)

## Executive Summary
Lateral stability in structural steel portal frames, industrial sheds, and multi-story skeletons is achieved through vertical wall bracing and horizontal roof diaphragm bracing networks. Bracing elements resist lateral wind and seismic shear, transferring loads to foundations via diagonal tension/compression members and gusset plate connections.

This module introduces `SourceSteelBracingGussetPlateShadowAuthority`, enabling authoritative shadow-mode extraction, 3D diagonal geometric calculation, and steel mass quantification of bracing members, gusset plates, and tensioner hardware directly from structural framing elevations and roof plans.

## Domain Model & Bracing Anatomy
1. **Bracing Configuration (`BracingConfigType`)**:
   - `X_BRACE`: Cross-braced diagonal pair intersecting at mid-bay.
   - `CHEVRON_V`: Inverted-V or V-bracing converging at beam midspan.
   - `K_BRACE`: Chevron configuration framed into mid-height column joints.
   - `SINGLE_DIAGONAL`: Single-direction tension tie rod or compression strut.
2. **Bracing Member Profile (`linear_mass_kg_m`)**:
   - Equal Angle (EA), Circular Hollow Section (CHS), Rectangular Hollow Section (RHS), or threaded solid round tie rods.
3. **Gusset Connection Plates (`GussetPlateSpec`)**:
   - Heavy structural steel plates (10mm to 20mm thickness, Grade 250/350 steel) anchored to column-beam or column-base nodes.
4. **Hardware Components**:
   - Turnbuckle clevis ends and high-tensile connection bolts.

## Mathematical Formulations
- **True 3D Diagonal Length (\(L_{diag}\))**:
  For endpoints \((X_1, Y_1, Z_1)\) and \((X_2, Y_2, Z_2)\):
  \[
  L_{diag} = \sqrt{(X_2 - X_1)^2 + (Y_2 - Y_1)^2 + (Z_2 - Z_1)^2}
  \]
- **Member Steel Mass (\(M_{member}\))**:
  \[
  M_{member} = \sum_{m} L_{diag, m} \times \text{linear\_mass\_kg\_m}_m
  \]
- **Gusset Plate Steel Mass (\(M_{gusset}\))**:
  \[
  M_{gusset} = \sum_{g} A_{plate, g} \times \left(\frac{t_{plate, g}}{1000}\right) \times 7850 \text{ kg/m}^3
  \]
- **Total Bracing System Steel Mass (\(M_{total}\))**:
  \[
  M_{total} = M_{member} + M_{gusset}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for structural node intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
