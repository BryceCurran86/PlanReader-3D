# Architecture Report: Source Structural Precast Hollowcore Slab Plank Shadow Authority (v1)

## Executive Summary
Suspended floor structures in precast concrete frames, composite steel-framed buildings, and masonry residential developments utilize extruded prestressed hollowcore concrete planks. Manufactured with high-strength concrete (50–60 MPa) and continuous hollow longitudinal cores, standard 1200mm wide units span between primary precast beams, structural steel beams, or loadbearing masonry walls. Precast floor plans specify plank depths (e.g. 150mm, 200mm, 250mm, 300mm, 400mm), span lengths, rip cut edge closures, shear key grout volumes, and composite structural topping thicknesses (50mm–75mm).

This module introduces `SourceHollowcoreSlabPlankShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for precast hollowcore plank layouts, net floor area, shear key longitudinal joints, and cast-in-place structural topping volume directly from precast shop drawings and structural framing plans.

## Domain Model & Plank Anatomy
1. **Plank Typology (`HollowcorePlankType`)**:
   - `STANDARD_EXTRUDED_PLANK`: Full-width 1200mm prestressed hollowcore unit.
   - `NARROW_CUT_PLANK`: Longitudinally sawn plank bridging residual bay widths.
   - `OPENING_PENETRATION_PLANK`: Factory or site formed core penetration with steel header hanger support.
   - `SOLID_FILLED_BEARING_PLANK`: Core ends grouted solid for concentrated bearing reactions.
2. **Structural Topping (`StructuralToppingType`)**:
   - `UNSTOPPED`: Bare precast floor with grouted shear keys.
   - `COMPOSITE_TOPPING`: Reinforced concrete topping slab (typically 50mm–75mm thick) forming a rigid floor diaphragm.
3. **Shear Key Longitudinal Joints (`shear_key_length_m`)**:
   - Continuous V-grooves between adjacent planks filled with non-shrink high-strength grout (typically ~0.0035 m³ grout per linear meter of joint).

## Mathematical Formulations
- **Net Plank Floor Area (\(A_{planks}\))**:
  \[
  A_{planks} = \sum_{i} \text{width}_i \cdot \text{length}_i
  \]
- **Composite Topping Concrete Volume (\(V_{topping}\))**:
  \[
  V_{topping} = \sum_{i \in \text{Composite}} A_{planks, i} \cdot \left(\frac{t_{topping, i}}{1000}\right)
  \]
- **Shear Key Grout Volume (\(V_{grout}\))**:
  \[
  V_{grout} = \sum_{j} L_{joint, j} \cdot 0.0035
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for plank boundary polygons and bearing lines.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
