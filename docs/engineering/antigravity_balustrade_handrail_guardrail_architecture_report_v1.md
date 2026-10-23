# Architecture Report: Source Balustrade, Handrail & Guardrail Fall Protection Shadow Authority (v1)

## Executive Summary
Fall protection barriers and accessibility handrails are critical statutory life safety installations required wherever building occupants are exposed to fall hazards exceeding 1.0 meter (balconies, terraces, mezzanines, stairs, ramps, and atrium voids). Building codes (NCC/BCA Part D3, AS 1428.1, AS 1170.1, AS 1288) enforce strict geometric height, continuity, and climbability constraints.

This module introduces `SourceBalustradeHandrailGuardrailShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for balustrade run lines, infill panels, post stanchions, and continuous graspable handrails directly from architectural plans, sections, and details.

## Domain Model & Barrier Anatomy
1. **Barrier Location (`BarrierLocationKind`)**:
   - `BALCONY_TERRACE`: External balcony or terrace (statutory minimum height 1100mm).
   - `STAIR_FLIGHT`: Sloped stair flight barrier (statutory minimum height 1000mm above pitch line).
   - `RAMP`: Pedestrian circulation ramp (1000mm barrier height).
   - `INTERNAL_VOID`: Mezzanine or void edge (1000mm to 1100mm height).
2. **Infill System (`BarrierInfillType`)**:
   - `FRAMELESS_GLASS`: Toughened laminated structural glass clamped in base spigots or recessed bottom channel.
   - `VERTICAL_BALUSTERS`: Powdercoated aluminium/steel pickets spaced at max 125mm clear openings.
   - `HORIZONTAL_WIRE_CABLE`: Stainless steel tensioned cables.
   - `PERFORATED_METAL`: Perforated aluminium mesh panels.
3. **Continuous Handrail (`has_continuous_handrail`)**:
   - Graspable circular/elliptical handrail (diameter 32mm–50mm) set at 865mm–1000mm AFFL, extending min 300mm horizontally at stair/ramp transitions per AS 1428.1.
4. **Post Stanchions**:
   - Structural support posts spaced at 900mm–1200mm centers along the run.

## Mathematical Formulations
- **Linear Balustrade Run (\(L_{balustrade}\))**:
  \[
  L_{balustrade} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Barrier Infill Vertical Face Area (\(A_{barrier}\))**:
  \[
  A_{barrier} = \sum_{i} L_{balustrade, i} \times \left(\frac{H_{barrier, i}}{1000}\right)
  \]
- **Handrail Total Length (\(L_{handrail}\))**:
  \[
  L_{handrail} = \sum_{i \in \text{Handrail}} (L_{balustrade, i} + \text{Extension}_{start, i} + \text{Extension}_{end, i})
  \]
- **Support Post Stanchion Count (\(N_{posts}\))**:
  \[
  N_{posts} = \sum_{i} \left(\left\lceil \frac{L_{balustrade, i}}{S_{post, i}} \right\rceil + 1\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for barrier polyline vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
