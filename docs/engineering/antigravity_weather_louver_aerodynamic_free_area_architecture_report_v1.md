# Architecture Report: Source Glazing Louver Bank & Weather Louver Aerodynamic Free Area Shadow Authority (v1)

## Executive Summary
Building envelopes, mechanical plant rooms, generator enclosures, and sub-station ventilation screens incorporate architectural and storm-resistant weather louvers. These systems must balance rain defense against the necessary airflow throughput defined by the Aerodynamic Net Free Area (AFA).

This module introduces `SourceWeatherLouverAerodynamicFreeAreaShadowAuthority`, providing an authoritative shadow-mode framework for parsing, validating, and quantifying weather louver banks, blade counts, aerodynamic free areas, perimeter frames, and rear bird/vermin mesh screens directly from facade elevations and mechanical schedules.

## Domain Model & Louver Anatomy
1. **Louver Blade Profile (`LouverBladeType`)**:
   - `SINGLE_STAGE_DRAINABLE`: Standard exterior drainable blade profile (nominal ~50% free area).
   - `TWO_STAGE_STORM`: Two-stage interlocking defensive blade profile rejecting wind-driven rain (~45% free area).
   - `ACOUSTIC_CHEVRON`: Sound-attenuating perforated chevron blades lined with acoustic mineral wool (~35% free area).
   - `CONTINUOUS_HORIZONTAL`: Architectural horizontal unbroken sightline louver.
2. **Gross Aperture Opening (`width_mm`, `height_mm`)**:
   - Out-to-out structural rough opening dimension in the facade or curtain wall frame.
3. **Aerodynamic Free Area (AFA)**:
   - Net unobstructed open area through which air flows without excessive pressure drop.
4. **Perimeter Extruded Frame (`frame_depth_mm`)**:
   - Surrounding aluminium channel frame securing the louver bank into the rough opening.
5. **Rear Bird / Vermin Mesh Screen**:
   - Stainless steel or galvanized wire mesh fixed to the rear face preventing intrusion by birds or pests.

## Mathematical Formulations
- **Gross Aperture Area (\(A_{gross}\))**:
  \[
  A_{gross} = \left(\frac{W_{mm}}{1000}\right) \times \left(\frac{H_{mm}}{1000}\right)
  \]
- **Net Aerodynamic Free Area (\(A_{free}\))**:
  \[
  A_{free} = A_{gross} \times \text{FreeAreaRatio}
  \]
- **Perimeter Frame Extrusion Length (\(L_{frame}\))**:
  \[
  L_{frame} = 2 \times \left(\frac{W_{mm} + H_{mm}}{1000}\right)
  \]
- **Estimated Blade Count (\(N_{blades}\))**:
  \[
  N_{blades} = \left\lceil \frac{H_{mm} - 100}{S_{pitch, mm}} \right\rceil
  \]
- **Rear Mesh Screen Surface Area (\(A_{mesh}\))**:
  \[
  A_{mesh} = A_{gross}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for louver opening corners.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
