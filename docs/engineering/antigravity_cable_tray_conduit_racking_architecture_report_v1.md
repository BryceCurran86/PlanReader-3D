# Architecture Report: Source Electrical Cable Tray, Ladder & Conduit Support Racking Shadow Authority (v1)

## Executive Summary
Large commercial data centers, hospital distribution risers, and industrial processing plants incorporate high-density overhead electrical cable containment systems. Electrical services layouts detail distribution pathways utilizing heavy-duty cable ladders (for main switchboard power sub-feeders), perforated sheet steel trays (for general lighting and power circuits), wire mesh basket trays (for structured communications/data cabling), and overhead unistrut trapeze racks supporting conduit banks. Containment plans identify tray widths (150mm to 900mm), side rail depths (50mm–150mm), support drop rod trapeze centers (typically 1.5m to 2.4m), and directional fittings (90° horizontal bends, tees, risers).

This module introduces `SourceCableTrayConduitRackingShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for electrical cable containment runs, width classifications, trapeze support assemblies, and junction fittings directly from electrical services floor plans and containment schedules.

## Domain Model & Containment Anatomy
1. **Support System Typology (`CableSupportSystemType`)**:
   - `HEAVY_DUTY_CABLE_LADDER`: Welded aluminium or hot-dip galvanized steel ladder with transverse rungs for heavy multicore power cables.
   - `PERFORATED_CABLE_TRAY`: Continuous pre-galvanized sheet steel tray with slotted drainage/ventilation holes.
   - `WIRE_MESH_BASKET_TRAY`: Spot-welded steel wire mesh basket (50mm x 100mm grid) for Cat6A and fiber optic data routes.
   - `UNISTRUT_CONDUIT_TRAPEZE_RACK`: Slotted steel unistrut channel suspended on threaded rods supporting grouped PVC/steel conduits.
2. **Tray Dimensions (`tray_width_mm`, `side_rail_depth_mm`)**:
   - Standard widths: 150mm, 300mm, 450mm, 600mm, 750mm, 900mm.
   - Rail depths: 50mm, 75mm, 100mm, 150mm.
3. **Suspension Support Trapeze (`support_spacing_m`)**:
   - M10/M12 zinc-plated threaded drop rods with channel nuts and bottom unistrut bearers spaced at 1.5m–2.4m intervals.
4. **Fittings & Bends (`fittings_count`, `fitting_type`)**:
   - Factory-made or site-fabricated 90° bends, equal tees, reducers, and vertical risers.

## Mathematical Formulations
- **Total Containment Linear Run (\(L_{containment}\))**:
  \[
  L_{containment} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Trapeze Hanger Supports Count (\(N_{supports}\))**:
  \[
  N_{supports} = \sum_{i} \left( \left\lceil \frac{\text{Length}(\text{centerline}_i)}{S_{support, i}} \right\rceil + 1 \right)
  \]
- **Linear Run by Tray Width (\(L_{W}\))**:
  \[
  L_{W} = \sum_{i \in \text{Width}(W)} \text{Length}(\text{centerline}_i)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for containment centerlines, tee junctions, and electrical riser nodes.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
