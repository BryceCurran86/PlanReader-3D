# Architecture Report: Source Multilevel Stair Tread, Riser & Flight Void Geometry Shadow Authority (v1)

## Executive Summary
In multi-storey building drawings, staircases connect vertical levels. In 2D floor plans, stairs appear as arrays of parallel tread lines crossed by a diagonal cut line and an "UP" or "DN" directional arrow.
Naive floor plan extraction suffers from two critical failures:
1. Treating stair tread lines as thin internal partition walls or joinery lines, cluttering wall topologies.
2. Failing to project the 3D stair void through the upper floor slab, causing ceiling and floor slabs to completely seal over vertical circulation shafts.

This authority parses stair flight boundaries, counts treads and risers, computes flight rise ($H = N_r \cdot R$), tread going length, pitch angle, and projects the exact 2D slab penetration void polygon in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 7 / Workstream B Item 12:** Vertical circulation shafts, stair geometries, and slab penetration voids.

## Flight Geometric Equations
Given:
- Number of risers $N_r$, unit riser height $R$, unit tread going $G$, clear flight width $W$.
- Flight direction `UP` or `DOWN`.

Calculations:
1. Tread count: $N_t = N_r - 1$.
2. Flight plan going length: $L = N_t \cdot G$.
3. Total vertical rise: $H = N_r \cdot R$.
4. Stair pitch angle: $\theta = \arctan(R / G) \cdot \frac{180}{\pi}$.
5. 3D walking line hypotenuse: $L_{walk} = \sqrt{L^2 + H^2}$.
6. Upper floor penetration void footprint: $[0, L] \times [0, W]$.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
