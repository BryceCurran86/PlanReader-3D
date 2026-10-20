# Architecture Report: Source Roof Drainage Gutter, Downpipe & Overflow Scupper Shadow Authority (v1)

## Executive Summary
Roof stormwater drainage infrastructure prevents hydraulic ponding, structural surcharge, and building envelope water ingress. Roof plans, roof plumbing layouts, and external elevations define linear gutters, rainwater collection heads, downpipes, and emergency overflow scuppers.

This module introduces `SourceRoofDrainageGutterDownpipeShadowAuthority`, providing an authoritative shadow-mode framework for parsing, validating, and quantifying roof drainage networks directly from 2D vector drawing primitives and plumbing callouts.

## Domain Model & Drainage Elements
1. **Internal Box Gutter (`BOX_GUTTER`)**:
   - Fabricated sheet metal gutter recessed between roof pitches or behind parapet walls.
   - Sized by sole width (min 300mm for commercial) and depth with longitudinal falls (typically 1:100 to 1:200).
2. **External Eaves Gutter (`EAVES_QUAD_GUTTER`, `HALF_ROUND_GUTTER`)**:
   - Suspended from fascia along the roof perimeter.
3. **Downpipes (`DownpipeSpec`)**:
   - Vertical drainage pipes (e.g., 90mm dia round or 100x75mm rectangular) dropping stormwater from gutter droppers/sumps to ground/underground stormwater lines.
4. **Rainwater Heads / Sumps (`RainwaterHeadSpec`)**:
   - External hopper boxes receiving box gutter discharge to provide air breaks and prevent siphonage into building cavities.
5. **Emergency Overflow Scuppers (`OverflowScupperSpec`)**:
   - Freeboard overflow openings cut through parapet walls designed to discharge total storm flow if primary outlets are obstructed.

## Mathematical Formulations
- **Linear Gutter Run (\(L_{gutter}\))**:
  \[
  L_{gutter} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Downpipe Vertical Drop Total (\(H_{dp}\))**:
  \[
  H_{dp} = \sum_{j} \text{Drop Height}_j
  \]
- **Gutter Sheet Development Girth (\(A_{gutter\_sheet}\))**:
  \[
  A_{gutter\_sheet} = \sum_{i} L_{gutter, i} \times \left(\frac{W_{sole} + 2 \times D_{sole} + 2 \times \text{Flange}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt snap tolerance on dropper and corner coordinates.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
