# Architecture Report: Source Suspended Slab Drop Panel & Column Capital Volume Shadow Authority (v1)

## Executive Summary
In suspended concrete flat plate and flat slab construction, high shear and bending stresses around column supports govern the structural capacity. Rather than thickening the entire floor plate, structural engineers specify localized slab drop panels and tapered column capitals.

This module introduces `SourceSlabDropPanelCapitalShadowAuthority`, providing authoritative shadow-mode extraction and quantification of drop panel footprints, additional concrete mass, stepped soffit perimeter edge formwork, and tapered capital frustum volumes directly from structural concrete drawings.

## Domain Model & Structural Elements
1. **Drop Panel (`DROP_PANEL`)**:
   - Prismatic rectangular or polygonal concrete slab thickening projecting beneath the uniform slab soffit.
   - Typically sized to extend at least L/6 into the span in each direction.
   - Requires stepped vertical edge formwork around its perimeter.
2. **Column Capital (`COLUMN_CAPITAL`)**:
   - Flared, conical, or inverted-pyramidal head at the column top supporting the slab or drop panel.
   - Characterized by top width/diameter, bottom column dimension, and vertical flare height.
3. **Band Beam / Drop Strip (`DROP_BEAM_STRIP`)**:
   - Continuous wide, shallow beam drop spanning between columns.

## Mathematical Formulations
- **Drop Panel Concrete Volume (\(V_{drop}\))**:
  \[
  V_{drop} = \sum_{i} A_{plan, i} \times \left(\frac{t_{drop, i}}{1000}\right)
  \]
- **Drop Panel Stepped Edge Formwork (\(A_{edge\_form}\))**:
  \[
  A_{edge\_form} = \sum_{i} P_{drop, i} \times \left(\frac{t_{drop, i}}{1000}\right)
  \]
  where \(P_{drop}\) is the drop panel perimeter.
- **Tapered Column Capital Volume (\(V_{capital}\))**:
  For an inverted pyramidal frustum with top area \(A_1\), bottom column area \(A_2\), and height \(h\):
  \[
  V_{capital} = \frac{h}{3} \left( A_1 + A_2 + \sqrt{A_1 A_2} \right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt snap tolerance on boundary vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
