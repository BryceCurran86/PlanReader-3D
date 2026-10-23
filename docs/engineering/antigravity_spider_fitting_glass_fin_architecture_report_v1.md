# Architecture Report: Source Glazing Spider Fitting & Point-Supported Glass Fin Facade Shadow Authority (v1)

## Executive Summary
Architectural entrance lobbies, multi-story atriums, and transparent curtain walls utilize point-supported glass facades anchored via precision-cast stainless steel spider fittings and articulated rotules. Rather than relying on opaque aluminium mullions, wind and seismic loads are transferred back to structural glass fins, tension rod trusses, or perimeter steel columns. Facade drawings detail spider bracket configurations (4-arm, 2-arm, 1-arm), rotule bolt diameters (M14, M16), glass fin heights and depths, and patch fittings.

This module introduces `SourceSpiderFittingGlassFinShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for point-fixed facade hardware, spider arm counts, rotule bolts, and structural glass fin assemblies directly from architectural glazing elevations and facade details.

## Domain Model & Facade Anatomy
1. **Spider Fitting Type (`SpiderFittingType`)**:
   - `FOUR_ARM`: Cross spider supporting 4 adjacent glass pane corners.
   - `TWO_ARM_180`: Linear 2-arm spider supporting 2 panes along vertical/horizontal joints.
   - `TWO_ARM_90`: Corner 2-arm spider for 90-degree facade corners.
   - `SINGLE_ARM`: 1-arm bracket for top/bottom perimeter glass corners.
   - `THREE_ARM`: 3-way spider at intermediate junction edges.
2. **Support System (`FinSupportType`)**:
   - `GLASS_FIN`: Heavy monolithic or laminated glass fin (e.g. 19mm toughened or 21.52mm laminated SGP interlayer) acting as a transparent vertical mullion.
   - `STEEL_COLUMN`: Stainless or painted carbon steel hollow section column.
   - `TENSION_ROD_TRUSS`: Pre-tensioned stainless steel wire rope or rod truss.
3. **Rotule Articulated Bolts (`rotule_dia_mm`, `rotule_count`)**:
   - Swivel-head articulated stainless steel bolts with conical or flat countersunk glass discs allowing rotational tolerance under wind suction/pressure.

## Mathematical Formulations
- **Total Rotule Bolts Takeoff (\(N_{rotules}\))**:
  \[
  N_{rotules} = \sum_{i} \text{arm\_count}_i
  \]
  where each spider arm anchors 1 rotule bolt through the glass pane.
- **Glass Fin Surface Area (\(A_{fin}\))**:
  \[
  A_{fin} = \sum_{j} \text{height}_j \cdot \left(\frac{\text{depth}_j}{1000}\right)
  \]
- **Total Fin Linear Height (\(H_{fin}\))**:
  \[
  H_{fin} = \sum_{j} \text{height}_j
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for spider fitting center points and fin locations.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
