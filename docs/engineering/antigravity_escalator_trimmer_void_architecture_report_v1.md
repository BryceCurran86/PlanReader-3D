# Architecture Report: Source Escalator & Moving Walkway Tridimensional Spatial Trimmer Void Shadow Authority (v1)

## Executive Summary
Large commercial retail centers, airport terminals, and multimodal transit hubs require high-capacity vertical pedestrian transportation systems including escalators and moving walkways (autowalks). Installing pre-assembled structural steel escalator trusses spanning across multiple floors necessitates large, precision-framed slab trimmer voids. These openings introduce significant structural discontinuous floor diaphragms requiring reinforced concrete edge beams or heavy structural steel trimmer channels, recessed bearing support pockets with neoprene vibration isolators, and life-safety draft curtains / drop smoke skirts (450mm–600mm deep) around the void perimeter to prevent smoke migration between atrium smoke reservoirs.

This module introduces `SourceEscalatorTrimmerVoidShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for escalator/moving walkway penetrations, opening throat geometry, slab trimmer linear edge runs, perimeter smoke baffle skirts, and 3D inclined travel distance directly from structural concrete and architectural vertical transport drawings.

## Domain Model & Escalator Void Anatomy
1. **Transportation Typology (`VerticalTransportationType`)**:
   - `COMMERCIAL_ESCALATOR_30_DEG`: Standard 30° incline escalator (step widths 800mm or 1000mm).
   - `PUBLIC_TRANSIT_ESCALATOR_35_DEG`: Compact/steep 35° incline escalator for transit stations.
   - `HORIZONTAL_MOVING_WALKWAY`: Flat 0° autowalk pallet system for airport concourses.
   - `INCLINED_MOVING_WALKWAY_12_DEG`: 10°–12° incline moving ramp accommodating shopping carts and luggage trolleys.
2. **Slab Trimmer Void (`void_polygon`, `void_width_m`, `void_length_m`)**:
   - Rectangular or trapezoidal opening cut through intermediate suspended concrete slab.
3. **Smoke Reservoir Draft Curtain (`has_smoke_baffle`, `baffle_depth_mm`)**:
   - Continuous toughened glass or non-combustible drop baffle suspended from slab soffit around opening perimeter (typically 450mm–600mm drop).
4. **Truss Bearing Pockets (`truss_bearing_reactions_kn`)**:
   - Recessed landing pockets at upper and lower floors transmitting heavy dead/live loads into structural frames.

## Mathematical Formulations
- **Opening Void Area (\(A_{void}\))**:
  \[
  A_{void} = \sum_{i} \text{ShoelaceArea}(\text{void\_polygon}_i)
  \]
- **Trimmer Beam Linear Run (\(P_{trimmer}\))**:
  \[
  P_{trimmer} = \sum_{i} \text{Perimeter}(\text{void\_polygon}_i)
  \]
- **Inclined Travel Distance (\(L_{travel}\))**:
  \[
  L_{travel} = \sum_{i} \frac{H_{rise, i}}{\sin(\theta_i)}
  \]
  where \(H_{rise}\) is vertical floor-to-floor rise and \(\theta\) is angle of inclination (e.g. 30° or 35°).
- **Draft Curtain / Smoke Skirt Area (\(A_{smoke\_skirt}\))**:
  \[
  A_{smoke\_skirt} = \sum_{i \in \text{SmokeBaffle}} P_{trimmer, i} \cdot \left(\frac{d_{baffle, i}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for void polygons and structural trimmer centerlines.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
