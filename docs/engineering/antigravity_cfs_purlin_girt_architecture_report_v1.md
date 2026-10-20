# Architecture Report: Source Cold-Formed Steel (CFS) Roof Purlin & Wall Girt Structural Framing Shadow Authority (v1)

## Executive Summary
Lightweight secondary structural framing in industrial sheds, commercial facilities, and residential multi-bay roofs consists of cold-formed galvanized steel C and Z purlins and wall girts. These members bridge primary rafters, portal frames, and perimeter columns, supporting metal roof decking and architectural wall cladding panels. Engineering framing layouts specify member designations (e.g. Z15015, Z20020, C20015, C15012), spacing/centers (e.g. 1200mm, 1500mm centers), span configuration (single, double, continuous lapped), and lateral bridging/sag rod systems.

This module introduces `SourceCFSPurlinGirtShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for cold-formed steel purlins, girts, continuous lap extensions, bridging lines, and mass (kg) calculations directly from structural roof and elevation framing plans.

## Domain Model & Framing Anatomy
1. **Framing Role (`CFSRole`)**:
   - `ROOF_PURLIN`: Sloped secondary roof member supporting roof sheeting and insulation.
   - `WALL_GIRT`: Horizontal secondary perimeter member spanning columns to carry wall cladding.
   - `EAVES_STRUT`: Heavy-duty strut section at roof/wall intersection transmitting longitudinal wind loads.
   - `FACIA_PURLIN`: Perimeter purlin providing eaves overhang and gutter support.
2. **Section Profile (`CFSSectionProfile`)**:
   - `Z_SECTION`: Lapped continuous section over rafters (e.g. Z20020).
   - `C_SECTION`: Single span or perimeter channel section (e.g. C15015).
   - `TOP_HAT`: Light-gauge hat section for direct battening (e.g. TH64, TH120).
3. **Continuity & Laps (`lap_length_mm`)**:
   - Lapped continuous purlins over internal supports require 10%–15% span overlap (typically 600mm–1200mm lap) providing continuity and moment capacity.
4. **Bridging System (`bridging_rows_count`)**:
   - Web-bolted anti-sag bridging lines restraining purlin/girt compression flanges against lateral-torsional buckling.

## Mathematical Formulations
- **Net Linear Run (\(L_{net}\))**:
  \[
  L_{net} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Total Linear Length with Laps (\(L_{gross}\))**:
  \[
  L_{gross} = \sum_{i} \left(\text{Length}(\text{centerline}_i) + \text{lap\_count}_i \cdot \frac{\text{lap\_length}_i}{1000}\right)
  \]
- **Steel Mass Takeoff (\(M_{steel}\))**:
  \[
  M_{steel} = \sum_{i} L_{gross, i} \cdot \rho_{linear, i}
  \]
  where \(\rho_{linear, i}\) is the linear mass density in kg/m derived from section designation (e.g., Z20020 \(\approx 4.48\) kg/m, C15015 \(\approx 2.89\) kg/m).

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for framing member endpoints and portal rafter intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
