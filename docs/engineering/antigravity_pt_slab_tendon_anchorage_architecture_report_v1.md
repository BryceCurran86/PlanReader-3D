# Architecture Report: Source Post-Tensioned (PT) Concrete Slab Tendon Band & Anchorage Pocket Shadow Authority (v1)

## Executive Summary
Post-tensioned (PT) concrete floor slabs provide efficient structural load-balancing and deflection control across large column grids. Structural PT plans define parabolically draped 7-wire prestressing steel strand tendons (banded along primary column strips and distributed across orthogonal spans) terminating in perimeter stressing pockets and blind dead-end anchors.

This module introduces `SourcePTSlabTendonAnchorageShadowAuthority`, enabling authoritative shadow-mode parsing, validation, and multi-component takeoff of post-tensioning tendon runs, individual strand masses, live stressing pockets, and non-shrink blockout grout infill directly from structural post-tensioning drawings.

## Domain Model & Tendon Anatomy
1. **Banded Tendons (`BANDED`)**:
   - Concentrated group of tendons (e.g., 4 to 8 strands per flat duct) bundled within a narrow column strip.
2. **Distributed Tendons (`DISTRIBUTED`)**:
   - Uniformly spaced tendons (e.g., 2 to 4 strands per duct at 1.2m–1.8m spacing) running perpendicular to banded lines.
3. **Live-End Stressing Anchorage (`LIVE_END_STRESSING`)**:
   - Cast-in anchor casting with a wedge plate, located inside a temporary perimeter edge formwork pocket (e.g., 150mm wide x 100mm high x 75mm deep) for hydraulic jack grip.
   - Requires non-shrink cementitious grout packing post-elongation lock-off.
4. **Dead-End / Blind Anchorage (`DEAD_END_BLIND`)**:
   - Fixed anchor buried directly inside the concrete pour without perimeter access.

## Mathematical Formulations
- **Total Strand Length (\(L_{strand}\))**:
  \[
  L_{strand} = \sum_{i} \text{Length}(\text{centerline}_i) \times N_{strands, i}
  \]
- **Prestressing Steel Mass (\(M_{steel}\))**:
  For standard 12.7mm 7-wire strand with nominal linear mass of \(0.785 \text{ kg/m}\):
  \[
  M_{steel} = L_{strand} \times 0.785 \text{ kg/m}
  \]
- **Live Stressing Pocket Grout Infill Volume (\(V_{pocket\_grout}\))**:
  \[
  V_{pocket\_grout} = \sum_{k \in \text{Live}} \left(\frac{W_{pocket, k}}{1000}\right) \times \left(\frac{H_{pocket, k}}{1000}\right) \times \left(\frac{D_{pocket, k}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for tendon endpoints and anchorage locations.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
