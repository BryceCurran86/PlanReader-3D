# Architecture Report: Source Precast Concrete Panel Joint & Sealant Backing Rod Shadow Authority (v1)

## Executive Summary
Precast concrete architectural facades and tilt-up industrial walls are constructed from modular reinforced concrete panels separated by vertical and horizontal movement control joints. Weatherproofing, acoustic isolation, and thermal integrity require continuous joint seals comprising closed-cell polyethylene foam backing rods and elastomeric polyurethane or silicone mastic sealants.

This module introduces `SourcePrecastPanelJointSealantShadowAuthority`, enabling authoritative shadow-mode extraction, spatial linking, and multi-component takeoff of precast concrete panels, joint networks, backing rods, and weather-sealant beads directly from architectural elevations and joint details.

## Domain Model & Joint Anatomy
1. **Precast Concrete Wall Panel (`PrecastPanelSpec`)**:
   - Monolithic solid precast or sandwich insulated concrete panel.
   - Characterized by width, height, panel thickness (e.g., 150mm–200mm), and boundary polyline.
2. **Vertical Control / Movement Joint (`PrecastJointSpec`)**:
   - Continuous gap between adjacent panel edges (nominal width 15mm–25mm) absorbing thermal expansion, shrinkage, and seismic drift.
3. **Backing Rod (`backing_rod_dia_mm`)**:
   - Compressible closed-cell polyethylene circular foam rod installed in the joint to set the sealant depth and prevent three-point adhesion.
4. **Elastomeric Sealant Bead (`sealant_depth_mm`)**:
   - Polyurethane or hybrid MS-polymer sealant gunned over the backing rod. Sized according to standard 2:1 width-to-depth aspect ratio (e.g., 20mm wide x 10mm deep).
   - Single exterior bead or double bead (exterior weather seal + interior air/smoke seal).

## Mathematical Formulations
- **Panel Concrete Volume (\(V_{conc}\))**:
  \[
  V_{conc} = \sum_{p} \text{Area}_p \times \left(\frac{t_{panel, p}}{1000}\right)
  \]
- **Joint Linear Run (\(L_{joint}\))**:
  \[
  L_{joint} = \sum_{j} \text{Length}(\text{centerline}_j)
  \]
- **Backing Rod Linear Length (\(L_{rod}\))**:
  \[
  L_{rod} = \sum_{j} L_{joint, j} \times N_{beads, j}
  \]
- **Sealant Volume in Liters (\(V_{sealant}\))**:
  \[
  V_{sealant} = \sum_{j} L_{joint, j} \times \left(\frac{W_{joint, j}}{1000}\right) \times \left(\frac{D_{seal, j}}{1000}\right) \times N_{beads, j} \times 1000 \text{ L/m}^3
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for panel corner and joint centerline vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
