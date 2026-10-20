# Architecture Report: Source Structural Foundation Strip Footing & Slab-on-Ground Edge Thickening Shadow Authority (v1)

## Executive Summary
Foundation engineering requires precise spatial modeling of continuous strip footings, slab-on-ground edge beams with brick rebates, and internal stiffening ribs. While architectural floor plans depict wall assemblies, structural footing layouts govern excavation trenches, concrete volumes, vapor barrier / damp-proof membrane extent, and perimeter edge formwork.

This module introduces `SourceSlabEdgeThickeningFootingShadowAuthority`, providing an authoritative, shadow-mode extraction and quantification framework for structural slab footings and ground-supported edge thickenings directly from 2D vector drawing primitives and structural annotations.

## Domain Model & Structural Types
1. **Edge Beam (`EDGE_BEAM`)**:
   - Continuous perimeter footing thickening supporting exterior walls.
   - Typically includes a stepped brick veneer rebate (e.g., 110mm-150mm wide x 50mm drop) to prevent water ingress and support outer masonry.
2. **Strip Footing (`STRIP_FOOTING`)**:
   - Continuous sub-grade mass or reinforced concrete footing beneath loadbearing core or masonry walls.
3. **Internal Stiffener Rib (`INTERNAL_STIFFENER`)**:
   - Intermediate ground beam stiffening large raft or waffle slabs under internal loadbearing or heavy partition walls.
4. **Pad Footing (`PAD_FOOTING`)**:
   - Isolated square/rectangular footing under structural columns or piers.

## Mathematical Formulations
- **Excavation Volume (\(V_{excav}\))**:
  \[
  V_{excav} = \sum_{i} L_i \times W_i \times D_i
  \]
  where \(L_i\) is the centerline polyline length, \(W_i\) is beam/footing width, and \(D_i\) is total excavation depth from finished level.
- **Concrete Footing Volume (\(V_{conc}\))**:
  Adjusts for slab rebate cutout on perimeter edge beams:
  \[
  V_{conc, edge} = L_{edge} \times (W_{edge} \times D_{edge} - W_{rebate} \times D_{rebate})
  \]
- **Formwork Contact Area (\(A_{form}\))**:
  Outside face of perimeter edge beams:
  \[
  A_{form} = \sum L_{edge} \times D_{edge}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: Coincident vertices snapped within 2.5 pt.
- **Zero Gold Dependency**: Pure algorithmic geometric processing; no project-specific constants.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
