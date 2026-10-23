# Architecture Report: Source Acoustic Wall Lining & Resilient Mount Separation Shadow Authority (v1)

## Executive Summary
Inter-tenancy boundaries, cinema complexes, recording studios, and mechanical plant room enclosures demand rigorous acoustic isolation. Airborne and impact sound transmission must be decoupled through discontinuous double-stud frames, resilient furring channels (RC-1), dense multi-leaf gypsum linings, and non-hardening acoustic perimeter sealants.

This module introduces `SourceAcousticWallLiningShadowAuthority`, enabling authoritative shadow-mode parsing, validation, and multi-leaf volumetric and area quantification of acoustic wall assemblies directly from partition schedule tags and wall assembly details.

## Domain Model & Acoustic Anatomy
1. **Structural Decoupling (`AcousticDecouplingType`)**:
   - `DOUBLE_STUD_DISCONTINUOUS`: Twin independent stud frames separated by a continuous air gap (typically 20mm-50mm) to break impact transmission.
   - `RESILIENT_CHANNEL_MOUNT`: Single stud frame fitted with horizontally mounted resilient steel channels (RC-1) spaced at 600mm centers.
   - `STAGGERED_STUD`: Alternating studs on a common wider track.
   - `DIRECT_FIXED`: Standard rigid structural fastening (baseline acoustic).
2. **Multi-Leaf Linings (`AcousticLiningLayer`)**:
   - High-density plasterboard (e.g., 13mm/16mm SoundBloc, Fyrchek, or acoustic gypsum).
   - Side A and Side B layer counts (e.g., 2 layers Side A + 2 layers Side B).
3. **Resilient Furring Channel Runs**:
   - Continuous horizontal channels attached at 600mm vertical increments along the wall height:
     \[
     N_{channels} = \left\lceil \frac{H_{wall}}{0.60} \right\rceil
     \]
4. **Perimeter Acoustic Mastic Sealant**:
   - Continuous beads applied along floor tracks, ceiling head tracks, and vertical abutment jambs:
     \[
     L_{sealant} = 2 \times (2 \times L_{wall} + 2 \times H_{wall})
     \]
     (top and bottom tracks + ends, double-beaded).

## Mathematical Formulations
- **Total Board Surface Area (\(A_{board}\))**:
  \[
  A_{board} = \sum_{w} L_{wall, w} \times H_{wall, w} \times (N_{layers, A, w} + N_{layers, B, w})
  \]
- **Resilient Channel Linear Run (\(L_{RC}\))**:
  \[
  L_{RC} = \sum_{w \in \text{RC-Mounted}} L_{wall, w} \times \left\lceil \frac{H_{wall, w}}{0.60} \right\rceil
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for adjacent polyline vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
