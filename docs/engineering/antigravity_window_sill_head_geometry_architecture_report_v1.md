# Architecture Report: Source Glazing Window Sill Height & Head Level Geometry Shadow Authority (v1)

## Executive Summary
In architectural plans, window symbols are drafted in 2D plan view as line strokes across wall openings. In 3D space, however, windows do not cut walls floor-to-ceiling. A window exists between an explicit Sill Height ($H_{sill}$) and Head Height ($H_{head}$). Above the head sits the structural lintel beam, and below the sill sits the sub-sill apron wall.

Naive extraction algorithms that treat window openings as floor-to-ceiling cuts discard sub-sill and lintel wall masses, creating massive false volumetric deductions.

This authority reconciles 2D window opening footprints with vertical level data, isolating the precise 3D glazing void volume ($V_{void} = L \times T \times H_{aperture}$) from retained wall masonry ($V_{apron} + V_{lintel}$) in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 9 / Workstream B Item 13:** Window geometry, opening hosts, and vertical level dimensions.

## Vertical Partitioning Equations
Given:
- Wall height $H_{wall}$, opening length $L$, host wall thickness $T$
- Sill height $H_{sill}$ and Head height $H_{head}$ ($0 \le H_{sill} < H_{head} \le H_{wall}$)

Vertical geometry components:
1. Glazing Aperture: $H_{aperture} = H_{head} - H_{sill}$
2. Sub-Sill Apron Wall: $H_{apron} = H_{sill}$
3. Overhead Lintel/Header Wall: $H_{lintel} = H_{wall} - H_{head}$
4. Glazing Aperture Void: $V_{void} = L \cdot T \cdot H_{aperture}$
5. Retained Wall Volume at Opening: $V_{retained} = L \cdot T \cdot (H_{apron} + H_{lintel})$

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
