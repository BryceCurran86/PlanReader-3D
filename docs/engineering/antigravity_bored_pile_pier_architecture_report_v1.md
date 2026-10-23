# Architecture Report: Source Structural Bored Pile & Pier Foundation Geotechnical Shadow Authority (v1)

## Executive Summary
Large commercial, residential, and industrial structures erected over compressible soils, uncontrolled fill, or sloping terrain rely on deep foundation systems comprising bored concrete piers, Continuous Flight Auger (CFA) piles, or driven piles keyed into solid bedrock. Geotechnical foundation layouts schedule pile diameters (e.g. 450mm, 600mm, 750mm, 900mm, 1200mm), design cut-off levels, overall drill depths, and minimum rock socket lengths.

This module introduces `SourceBoredPilePierShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for deep foundation pile elements, total linear drilling depth, rock socket verification, and cylindrical concrete displacement volume directly from structural foundation plans and schedules.

## Domain Model & Pile Anatomy
1. **Pile System Type (`PileType`)**:
   - `BORED_CAST_IN_PLACE`: Open or cased rotary bored pile with reinforced cage and tremie-poured concrete.
   - `CONTINUOUS_FLIGHT_AUGER`: CFA pile augered with hollow stem and pumped concrete/grout under pressure.
   - `DRIVEN_PRECAST_CONCRETE`: Impact-driven square or octagonal prestressed precast concrete pile.
   - `STEEL_SCREW_PILE`: Helical torque-installed steel pier shaft.
   - `MICROPILE`: High-capacity small-diameter drilled and grouted steel micropile (100mm–300mm).
2. **Geotechnical Socketing (`rock_socket_length_m`)**:
   - Embedded length socketed into designated stratum (e.g. Class II / III Sandstone, Siltstone, or Basalt bedrock).
3. **Pile Groups & Caps (`pile_cap_id`)**:
   - Association of individual piles into 1-pile, 2-pile, 3-pile, or 4-pile caps supporting structural columns or core walls.

## Mathematical Formulations
- **Total Pile Drilled Length (\(L_{total}\))**:
  \[
  L_{total} = \sum_{i} \text{depth}_i
  \]
- **Cylindrical Concrete Volume (\(V_{conc}\))**:
  \[
  V_{conc} = \sum_{i} \pi \cdot \left(\frac{D_i}{2000}\right)^2 \cdot \text{depth}_i
  \]
  where \(D_i\) is the pile diameter in millimeters, and \(\text{depth}_i\) is in meters.
- **Total Rock Socket Length (\(L_{socket}\))**:
  \[
  L_{socket} = \sum_{i} \text{rock\_socket}_i
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for pile center coordinates.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
