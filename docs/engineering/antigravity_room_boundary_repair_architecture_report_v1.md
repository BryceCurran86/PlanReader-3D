# Architecture Report: Source Room Polyline Self-Intersection & Degenerate Boundary Repair Shadow Authority (v1)

## Executive Summary
During 2D floor plan extraction, room polygon boundaries are traced along enclosing wall faces, doorways, and alcoves. Edge tracing frequently produces topological anomalies:
1. Self-intersecting bowtie (figure-eight) polygons where two non-adjacent wall faces cross, corrupting standard shoelace area calculations.
2. Collapsed antenna spikes ($A \to B \to A$) where the tracer walks into a wall cavity or door jamb and backtracks along the identical line.
3. Collinear micro-vertices and duplicate vertices within snap tolerance (2.5 pt) creating degenerate zero-length segments.

This authority inspects room boundary polylines, identifies specific defect classes, strips antennas and micro-vertices, untangles self-intersections into simple Jordan polygons, and guarantees positive planar area in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 11:** Room boundary closure, geometry repair, and physical perimeter takeoff.

## Defect Classification & Repair Pipeline
1. **Defect Types:**
   - `BOWTIE_SELF_INTERSECTION`: Non-adjacent edge crossing.
   - `COLLAPSED_ANTENNA_SPIKE`: Backtracking zero-width excursion ($A \to B \to A$).
   - `DUPLICATE_OR_MICRO_VERTEX`: Consecutive vertices closer than `snap_tolerance_pt` (2.5 pt).
   - `COLLINEAR_REDUNDANT_VERTEX`: Intermediate vertex on a straight boundary segment.

2. **Repair Stages:**
   - **Stage 1 (Micro-Vertex Cleanup):** Filter vertices separated by less than `snap_tolerance_pt`.
   - **Stage 2 (Antenna Pruning):** Remove vertices where incoming and outgoing vectors are anti-parallel (backtracking).
   - **Stage 3 (Collinear Reduction):** Collapse intermediate points on straight edges.
   - **Stage 4 (Self-Intersection Untangling):** Identify edge crossing points and split multi-loop figures into simple closed Jordan polygons.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
