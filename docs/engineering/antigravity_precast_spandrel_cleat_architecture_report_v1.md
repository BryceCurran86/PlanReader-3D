# Architecture Report: Source Precast Architectural Facade Spandrel Panel & Tie-Back Cleat Shadow Authority (v1)

## Executive Summary
Mid-rise and high-rise commercial office developments incorporate architectural precast concrete spandrel panels spanning perimeter column bays between bands of ribbon glazing. Serving as exterior building envelope, fire-separation apron between vertically adjacent floors, and window-sill substrate, these panels must resist severe out-of-plane wind suction and seismic inter-story building drift. Precast erection schedules specify panel typology (monolithic solid panels vs thermally broken insulated sandwich panels), dimensions (length 6.0m–9.0m, height 1.2m–1.8m, thickness 150mm–250mm), and engineered structural connections (dual gravity dead-load bearing brackets and slotted seismic/wind tie-back cleats).

This module introduces `SourcePrecastSpandrelCleatShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for architectural facade spandrel panels, gross surface area, precast concrete volume, structural dead-load bearing angles, and slotted wind tie-back cleats directly from facade elevations and precast connection details.

## Domain Model & Spandrel Anatomy
1. **Spandrel Panel Typology (`SpandrelPanelType`)**:
   - `SOLID_PRECAST_SPANDREL`: Monolithic reinforced concrete panel (150mm–200mm thickness).
   - `INSULATED_SANDWICH_SPANDREL`: Composite sandwich consisting of 75mm outer architectural wythe, 50mm rigid PIR insulation, and 100mm structural concrete backing wythe.
   - `INTEGRATED_WINDOW_SILL_SPANDREL`: Monolithic panel cast with integrated sloping window sill and drip bead.
   - `CURVED_RADIUS_SPANDREL`: Radiused corner panel bridging facade transitions.
2. **Structural Connection Hardware (`CleatConnectionType`)**:
   - `GRAVITY_BEARING_BRACKET`: Heavy fabricated steel angle bracket transferring panel dead load into perimeter edge beams/columns (2 per panel).
   - `TIE_BACK_SLOTTED_CLEAT`: Slotted steel cleat with PTFE low-friction washers accommodating horizontal thermal/seismic movement while resisting wind load (2 to 4 per panel).
3. **Panel Geometry (`panel_length_m`, `panel_height_m`, `thickness_mm`)**:
   - Length typically matches column grid bay (e.g. 6.0m to 8.4m); height spans from slab top to window sill (typically 1.2m to 1.5m).

## Mathematical Formulations
- **Total Spandrel Elevation Area (\(A_{spandrel}\))**:
  \[
  A_{spandrel} = \sum_{i} \text{Length}_i \cdot \text{Height}_i
  \]
- **Precast Concrete Volume (\(V_{conc}\))**:
  \[
  V_{conc} = \sum_{i} A_{spandrel, i} \cdot \left(\frac{t_{conc, i}}{1000}\right)
  \]
  where \(t_{conc}\) is the net concrete thickness in millimeters.
- **Connection Hardware Counts (\(N_{gravity}\), \(N_{tieback}\))**:
  \[
  N_{gravity} = \sum_{i} \text{gravity\_brackets}_i, \quad N_{tieback} = \sum_{i} \text{tieback\_cleats}_i
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for panel boundary polygons and connection cleat anchor nodes.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
