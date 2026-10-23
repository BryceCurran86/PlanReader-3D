# Architecture Report: Source Access Floor Raised Flooring System & Pedestal Stanchion Shadow Authority (v1)

## Executive Summary
Data centers, server server equipment rooms, broadcast suites, and commercial office trading floors utilize modular raised access flooring systems. These assemblies establish an accessible underfloor plenum for high-density power distribution, structured fiber-optic cabling, and underfloor air distribution (UFAD).

This module introduces `SourceAccessFloorPedestalShadowAuthority`, providing an authoritative shadow-mode framework for extracting raised flooring zone boundaries, modular 600x600mm floor panels, adjustable steel pedestal stanchions, perimeter fascia closures, and underfloor plenum volumes directly from architectural floor plans and finish schedules.

## Domain Model & Raised Floor Anatomy
1. **Access Floor Panel (`AccessFloorGrade`)**:
   - Standard 600mm x 600mm steel-encapsulated cementitious core panel (0.36 m² surface area).
   - Classified by concentrated load rating: `MEDIUM_GRADE` (3.0 kN), `HEAVY_GRADE` (4.5 kN), `EXTRA_HEAVY_GRADE` (6.7 kN).
2. **Finished Floor Height (`ffh_mm`)**:
   - Elevation of the finished floor panel top surface above the bare concrete structural slab (typically 150mm to 600mm).
3. **Pedestal Stanchion Grid**:
   - Threaded galvanized steel support posts with sound-damping neoprene head gaskets set on a 600mm x 600mm module.
4. **Perimeter Fascia & Edge Trim**:
   - Vertical closures and edge angles sealing the floor perimeter at step-downs and transitions.
5. **Underfloor Plenum Void**:
   - Net air volume available beneath the panels for pressurized conditioned air supply.

## Mathematical Formulations
- **Net Raised Floor Surface Area (\(A_{floor}\))**:
  \[
  A_{floor} = \text{PolygonArea}(\text{boundary})
  \]
- **Full Modular Panel Count (\(N_{panels}\))**:
  \[
  N_{panels} = \left\lceil \frac{A_{floor}}{0.36} \right\rceil
  \]
- **Pedestal Stanchion Count (\(N_{pedestals}\))**:
  For an orthogonal grid with boundary perimeter \(P\):
  \[
  N_{pedestals} \approx \left\lceil \frac{A_{floor}}{0.36} + \frac{P}{1.20} + 1 \right\rceil
  \]
- **Underfloor Plenum Air Volume (\(V_{plenum}\))**:
  \[
  V_{plenum} = A_{floor} \times \left(\frac{\text{ffh\_mm}}{1000}\right)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for room boundary vertices.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
