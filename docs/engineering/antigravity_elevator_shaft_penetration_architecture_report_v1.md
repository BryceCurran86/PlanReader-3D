# Architecture Report: Source Elevator / Lift Core Shaft Vertical Penetration Shadow Authority (v1)

## Executive Summary
Elevator and lift core shafts form critical vertical continuous circulation and shear core structures in multi-story buildings. Shafts require precise vertical clearance alignment, pit depth below the lowest finished slab, overhead clearance / machine room-less (MRL) overrun height, structural fire-rated wall enclosures, guide rail fixings, and floor-by-floor entrance landing door openings.

This module introduces `SourceElevatorShaftPenetrationShadowAuthority`, providing an authoritative shadow-mode framework for extracting, linking, and quantifying elevator core shafts across multi-level architectural and structural drawing sets.

## Domain Model & Vertical Anatomy
1. **Clear Hoistway (`clear_width_mm`, `clear_depth_mm`)**:
   - Internal unobstructed shaft dimensions required for elevator car travel, counterweight clearance, and guide rails.
2. **Shaft Pit (`pit_depth_mm`)**:
   - Sub-slab void below the lowest finished landing datum (typically 1200mm to 1600mm) housing car safety buffers, tension pulleys, and drainage sump.
3. **Shaft Overrun (`overrun_height_mm`)**:
   - Vertical clearance above the top landing finished floor level to the underside of the shaft roof slab (typically 3600mm to 4800mm) accommodating top-of-car safety zones and hoist equipment.
4. **Enclosure Walls**:
   - Structural reinforced concrete or fire-rated core blockwork surrounding the hoistway.
5. **Landing Door Openings**:
   - Sized per served level (e.g., 900mm-1100mm wide x 2100mm high) penetrating the shaft front wall.
6. **Guide Rails**:
   - Pair of vertical steel T-rails for the car plus pair for counterweight running the entire shaft height.

## Mathematical Formulations
- **Total Vertical Travel Height (\(H_{total}\))**:
  \[
  H_{total} = \text{Pit Depth} + \sum_{l=1}^{N-1} (\text{Level Floor-to-Floor Height}_l) + \text{Overrun Height}
  \]
- **Shaft Enclosure Gross Wall Area (\(A_{gross\_wall}\))**:
  \[
  A_{gross\_wall} = P_{shaft\_centerline} \times H_{total}
  \]
- **Net Enclosure Wall Area (\(A_{net\_wall}\))**:
  \[
  A_{net\_wall} = A_{gross\_wall} - \sum_{k=1}^{N_{doors}} (W_{door, k} \times H_{door, k})
  \]
- **Guide Rail Linear Takeoff (\(L_{rails}\))**:
  \[
  L_{rails} = 4 \times H_{total} \quad \text{(for 2 car rails + 2 counterweight rails)}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for shaft corner alignment.
- **Zero Gold Dependency**: Pure algorithmic geometric model; no project-specific constants.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
