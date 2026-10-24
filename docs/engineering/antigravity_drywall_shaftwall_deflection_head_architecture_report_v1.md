# Architecture Report: Source Fire-Rated Drywall Partition Shaftwall & Deflection Head Joint Shadow Authority (v1)

## Executive Summary
Commercial high-rise interior fitouts and institutional construction utilize lightweight cold-formed steel drywall partition systems terminating at suspended concrete slabs. Due to suspended floor deflection under live load, temperature shifts, and concrete creep, rigid top-of-wall connections would crush plasterboard linings or buck steel studs. Consequently, full-height fire-rated partitions (1-hr to 3-hr FRL) and vertical shaft enclosures (elevator shafts, fire stairs, mechanical risers) require engineered deflection head assemblies (slotted deflection tracks, deep-leg nested tracks, intumescent firestop pillows/mastics) accommodating 15mm–50mm vertical slab displacement. Shaftwall assemblies utilize specialized C-H or I studs accommodating 25mm thick gypsum shaftliner panels installed entirely from outside the shaft.

This module introduces `SourceDrywallShaftwallDeflectionHeadShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for fire-rated drywall partition layouts, deflection head linear runs, wall surface area, and shaftwall core board takeoffs directly from architectural partition plans and wall type schedules.

## Domain Model & Wall Assembly Anatomy
1. **Partition System (`DrywallSystemType`)**:
   - `STANDARD_FIRE_PARTITION`: C-stud wall lined both sides with 13mm/16mm fire-rated plasterboard (FRL -/60/60 to -/120/120).
   - `SHAFTWALL_SYSTEM`: C-H or I-stud framing with 25mm thick gypsum Shaftliner board slotted into stud webs plus corridor linings (2-hr / 3-hr fire barrier).
   - `HIGH_WALL_CORRIDOR`: Heavy 0.75mm/1.15mm BMT steel studs spanning tall floor-to-soffit voids (>4.5m).
   - `ACOUSTIC_DOUBLE_STUD`: Twin independent stud tracks separated by 20mm air cavity for high Rw/STC isolation.
2. **Deflection Head Track (`DeflectionHeadType`)**:
   - `SLOTTED_DEFLECTION_TRACK`: Specialized top track with vertical guide slots allowing screw anchors to slide during slab deflection.
   - `DEEP_LEG_NESTED_TRACK`: 50mm–75mm deep-leg track over nested inner stud runners.
   - `FIRE_RATED_INTUMESCENT_TRACK`: Track with pre-affixed intumescent elastomeric seals maintaining fire stop during live movement.
3. **Deflection Allowance (`deflection_allowance_mm`)**:
   - Vertical movement capacity: typically 15mm, 20mm, 25mm, 35mm, or 50mm.

## Mathematical Formulations
- **Partition Linear Run (\(L_{wall}\))**:
  \[
  L_{wall} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Deflection Head Track Run (\(L_{deflection}\))**:
  \[
  L_{deflection} = \sum_{i \in \text{FullHeight}} \text{Length}(\text{centerline}_i)
  \]
- **Wall Surface Area (\(A_{wall}\))**:
  \[
  A_{wall} = \sum_{i} \text{Length}(\text{centerline}_i) \cdot H_{wall, i}
  \]
- **Shaftliner 25mm Core Board Area (\(A_{shaftliner}\))**:
  \[
  A_{shaftliner} = \sum_{i \in \text{Shaftwall}} \text{Length}(\text{centerline}_i) \cdot H_{wall, i}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for wall centerlines and partition T-junction intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
