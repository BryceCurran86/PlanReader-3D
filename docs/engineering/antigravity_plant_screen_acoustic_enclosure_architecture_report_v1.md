# Architecture Report: Source Architectural Metal Louvered Plant Room Screen & Acoustic Enclosure Shadow Authority (v1)

## Executive Summary
Commercial rooftops, hospital utility zones, and data centers house heavy mechanical services (air-cooled chillers, cooling towers, generator sets, VRV condensers) requiring architectural screening from street sightlines and strict acoustic boundary compliance. Architectural roof plans and facade elevations specify plant screens balancing airflow intake with sound insertion loss and weather protection. These systems comprise modular or continuous extruded aluminium sight screens (inverted-Y or chevron blades), heavy acoustic louvers packed with rockwool insulation, galvanized steel structural support posts (SHS stanchions) bolted to concrete upstands, and matching louvered access doors.

This module introduces `SourcePlantScreenAcousticEnclosureShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for mechanical plant screens, acoustic enclosure walls, linear perimeter runs, elevation face area, support post counts, and integrated access door hardware directly from roof layout drawings and screen schedules.

## Domain Model & Screen Anatomy
1. **Screen Typology (`PlantScreenType`)**:
   - `ARCHITECTURAL_SIGHT_SCREEN`: Inverted chevron/slanted aluminium blades providing 100% visual screening with ~50% free airflow area.
   - `CONTINUOUS_ACOUSTIC_LOUVER`: Deep acoustic louver blades (150mm–300mm depth) with perforated undersides and high-density mineral wool infill for equipment noise attenuation.
   - `WEATHERPROOF_PLANT_ENCLOSURE`: 2-stage weather louvers preventing horizontal rain penetration to sensitive electrical equipment.
   - `SOLID_ACOUSTIC_BARRIER_PANEL`: Solid steel/composite sandwich acoustic panels enclosing noisy generators.
2. **Support Framing (`ScreenSupportType`)**:
   - `STRUCTURAL_STEEL_SHS`: Hot-dip galvanized square hollow section posts (e.g. 100x100 SHS) spaced at 1.5m–2.4m centers.
   - `ALUMINIUM_BOX_MULLIONS`: Extruded aluminium structural box sections.
   - `CANTILEVER_PLINTH_STANCHION`: Base-plated steel stanchions anchored to concrete hob plinths.
3. **Screen Geometry (`screen_height_m`, `post_spacing_m`)**:
   - Screen height typically 2.0m, 2.4m, 3.0m, or 3.6m to mask roof plant equipment.
   - Support post spacing typically 1.8m to 2.4m based on site wind design pressure.
4. **Integrated Access Doors (`doors_count`, `door_width_m`)**:
   - Flush matching louvered single or double doors providing maintenance access.

## Mathematical Formulations
- **Perimeter Screen Linear Run (\(L_{screen}\))**:
  \[
  L_{screen} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Elevation Face Area (\(A_{screen}\))**:
  \[
  A_{screen} = \sum_{i} \text{Length}(\text{centerline}_i) \cdot H_{screen, i}
  \]
- **Structural Support Posts Count (\(N_{posts}\))**:
  \[
  N_{posts} = \sum_{i} \left(\left\lceil \frac{\text{Length}(\text{centerline}_i)}{S_{post, i}} \right\rceil + 1\right)
  \]
  where \(S_{post, i}\) is post spacing in meters.

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for screen centerlines, corners, and access door boundaries.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
