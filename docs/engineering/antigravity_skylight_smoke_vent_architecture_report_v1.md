# Architecture Report: Source Roof Skylight & Smoke Relief Vent Curb Framing Shadow Authority (v1)

## Executive Summary
Commercial distribution centers, atrium roofs, and multi-story retail complexes feature specialized roof penetrations providing natural illumination and emergency life-safety smoke containment. Automatic Smoke and Heat Exhaust Ventilators (ASHEVs conforming to EN 12101-2 or AS 2665) and architectural day-lighting skylights require rigid structural upstand kerbs/curbs elevated 150mm–300mm above finished roof waterproofing lines to prevent ponding and wind-driven rain penetration. Architectural roof plans and engineering schedules identify opening dimensions (e.g. 1200mm × 2400mm), curb construction (insulated steel, precast concrete, timber), fall-arrest safety mesh, and aerodynamic free ventilation areas.

This module introduces `SourceSkylightSmokeVentShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for roof skylight and smoke exhaust units, perimeter curb linear runs, opening throat areas, and aerodynamic ventilation capacity directly from architectural roof plans and penetration schedules.

## Domain Model & Penetration Anatomy
1. **Device Typology (`RoofVentSkylightType`)**:
   - `FIXED_SKYLIGHT_DOME`: Fixed double-glazed or polycarbonate barrel vault / dome for daylighting.
   - `OPERABLE_VENT_SKYLIGHT`: Motorized or pneumatic actuator roof window for natural ventilation.
   - `AUTOMATIC_SMOKE_HEAT_VENT`: Certified emergency smoke release hatch triggered by thermal links or BMS smoke alarm signal.
   - `ROOF_ACCESS_HATCH`: Gas-strut counterbalanced insulated hatch door for maintenance roof access.
2. **Curb Framing (`CurbConstructionType`)**:
   - `INSULATED_STEEL_UPSTAND`: Pre-fabricated double-walled galvanized steel curb with 50mm mineral wool core.
   - `STRUCTURAL_TIMBER_KERB`: Laminated or solid timber kerb upstand bolted to roof trimmers.
   - `PRECAST_CONCRETE_UPSTAND`: Cast-in concrete curb collar integrated with structural slab.
   - `ALUMINIUM_EXTRUDED_CURB`: Extruded thermally broken aluminium curb system.
3. **Safety Mesh & Glazing (`has_safety_mesh`, `glazing_type`)**:
   - Fall-prevention welded steel wire safety mesh (300J impact rated) spanning the throat to prevent worker fall-through accidents during roof maintenance.

## Mathematical Formulations
- **Opening Throat Area (\(A_{throat}\))**:
  \[
  A_{throat} = \sum_{i} \text{width}_i \cdot \text{length}_i
  \]
- **Perimeter Curb Linear Run (\(P_{curb}\))**:
  \[
  P_{curb} = \sum_{i} 2 \cdot (\text{width}_i + \text{length}_i)
  \]
- **Aerodynamic Free Area (\(A_v\))**:
  \[
  A_v = \sum_{i \in \text{SmokeVent}} A_{throat, i} \cdot C_v
  \]
  where \(C_v\) is the discharge coefficient (typically \(0.65\) for 90-degree opening single/double flap vents).

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for curb bounding boxes and roof opening trimmer intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
