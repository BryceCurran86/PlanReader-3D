# Architecture Report: Source Parapet Wall Flashing & Roof Capping Linear Takeoff Shadow Authority (v1)

## Executive Summary
Parapets define the perimeter roof boundary on commercial and multi-residential structures. While general roof plans display roof areas, the parapet envelope details govern specialized metal flashing, capping sheets, waterproof membrane upstands, and counter-flashing reglets.

This module introduces `SourceParapetCappingFlashingShadowAuthority`, enabling authoritative shadow-mode parsing, validation, and geometric quantification of parapet flashings and coping caps directly from roof plan perimeters and detail section annotations.

## Domain Model & Envelope Anatomy
1. **Parapet Upstand (`ParapetSegmentSpec`)**:
   - Vertical wall extension above the structural slab/roof deck (typically 300mm to 1200mm).
2. **Coping / Capping Flashing (`CappingMaterial`)**:
   - Protective weather-resistant cap (Colorbond steel, folded aluminium, copper, zinc, precast concrete) across the top of the parapet.
   - Requires cross-fall slope inward to drain rainwater onto the roof, with drip edges overhanging on both faces.
   - Girth: Flat sheet development width including folds, hem, and drip returns (typically 300mm to 600mm girth).
3. **Membrane Waterproofing Upstand**:
   - Liquid-applied or sheet waterproofing membrane turned up the internal vertical face (standard minimum 150mm to 300mm).
4. **Counter-Flashing & Reglet Chase**:
   - Over-flashing mechanically fastened or tucked into a sawcut reglet in concrete/masonry to protect the top edge of the waterproof membrane.

## Mathematical Formulations
- **Linear Parapet Length (\(L_{parapet}\))**:
  \[
  L_{parapet} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Capping Flashing Developed Area (\(A_{cap}\))**:
  \[
  A_{cap} = \sum_{i} L_{parapet, i} \times \left(\frac{\text{girth\_mm}_i}{1000}\right)
  \]
- **Membrane Upstand Surface Area (\(A_{mem}\))**:
  \[
  A_{mem} = \sum_{i} L_{parapet, i} \times \left(\frac{\text{turnup\_mm}_i}{1000}\right)
  \]
- **Counter-Flashing Length (\(L_{counter}\))**:
  \[
  L_{counter} = L_{parapet}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for segment vertex connectivity.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
