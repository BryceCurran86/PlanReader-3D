# Architecture Report: Source Structural Timber Laminated Veneer Lumber (LVL) & Glulam Beam Framing Shadow Authority (v1)

## Executive Summary
Modern architectural timber framing and mass timber structures incorporate high-performance engineered wood products (EWPs) including Laminated Veneer Lumber (LVL) and Glue-Laminated Timber (Glulam). With significantly higher bending strength and dimensional stability than solid sawn timber, LVL (e.g. e14, e16, hySPAN, smartLVL) and Glulam (e.g. GL17c, GL18, GL20) members span wide structural clear spans, carrying roof loads over large sliding doors, garage openings, open-plan floor girders, and architectural cathedral ceilings. Structural framing plans schedule member cross-sections (e.g. 240x45, 300x63, 2/300x45, 360x65, 450x85), multi-ply laminations, and design spans.

This module introduces `SourceLVLGlulamTimberShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for engineered timber beams, built-up multi-ply assemblies, net/gross linear lengths, and timber volume (m³) directly from structural timber layout plans and framing schedules.

## Domain Model & Timber Framing Anatomy
1. **Engineered Timber Category (`EngineeredTimberType`)**:
   - `LAMINATED_VENEER_LUMBER_LVL`: Rotary peeled wood veneers bonded with phenolic adhesive (e.g. e14, e16).
   - `GLUE_LAMINATED_TIMBER_GLULAM`: Finger-jointed dimensional timber laminations (e.g. GL13, GL17c, GL18).
   - `CROSS_LAMINATED_TIMBER_BEAM_CLT`: Solid timber mass panel beam.
   - `SOLID_SAWN_F_GRADE`: Traditional sawn softwood/hardwood (e.g. F7, F17, MGP10).
2. **Structural Role (`TimberFramingRole`)**:
   - `OPENING_LINTEL`: Header beam spanning window/door openings.
   - `ROOF_RIDGE_BEAM`: Apex beam supporting rafters in cathedral ceilings.
   - `FLOOR_BEARER_GIRDER`: Primary floor substructure beam supporting joists.
   - `PORTAL_RAFTER`: Sloped roof beam in timber portal frames.
   - `CANTILEVER_VERANDAH_BEAM`: Balcony or canopy projecting beam.
3. **Multi-Ply Configuration (`plies_count`, `ply_width_mm`, `depth_mm`)**:
   - Beams frequently specified as multi-ply built-up sections, e.g. "2/300x45 LVL" (2 plies of 45mm width = 90mm total width × 300mm depth).

## Mathematical Formulations
- **Gross Beam Linear Run (\(L_{beam}\))**:
  \[
  L_{beam} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Single-Ply Equivalent Linear Run (\(L_{equiv}\))**:
  \[
  L_{equiv} = \sum_{i} \text{plies}_i \cdot \text{Length}(\text{centerline}_i)
  \]
- **Timber Solid Volume (\(V_{timber}\))**:
  \[
  V_{timber} = \sum_{i} \text{plies}_i \cdot \left(\frac{b_i \cdot d_i}{10^6}\right) \cdot \text{Length}(\text{centerline}_i)
  \]
  where \(b_i\) is individual ply width (mm), \(d_i\) is beam depth (mm), and \(\text{Length}\) is in meters.

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for beam endpoints and column/wall bearing nodes.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
