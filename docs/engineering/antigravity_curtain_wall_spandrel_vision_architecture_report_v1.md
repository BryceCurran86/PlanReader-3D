# Architecture Report: Source Curtain Wall Spandrel Panel & Vision Glazing Partition Shadow Authority (v1)

## Executive Summary
Commercial curtain wall facade systems consist of modular vertical bays partitioned into transparent vision glazing and opaque insulated spandrel panels.
Naive 2D facade extraction treats curtain wall runs as uniform glass planes, leading to:
1. Complete omission of spandrel backpan insulation (e.g. 50mm mineral wool / rockwool) and perimeter slab edge horizontal smoke/fire seals.
2. Inaccurate energy/thermal calculations, misrepresenting opaque insulated zones as uninsulated transparent glass.

This authority partitions curtain wall bays into vision glazing ($[H_{sill}, H_{head}]$) and opaque spandrels ($[0, H_{sill}] \cup [H_{head}, H_{f2f}]$), quantifying vision glass area, spandrel panel area, backpan insulation volume, and perimeter slab edge firestopping in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 10 / Workstream B Item 13:** Curtain wall envelope geometry, spandrel panels, and vision glazing takeoff.

## Vertical Partitioning Equations
Given:
- Bay clear width $W_{bay}$ and story floor-to-floor height $H_{f2f}$.
- Vision sill elevation $H_{sill}$ and head elevation $H_{head}$ ($0 \le H_{sill} < H_{head} \le H_{f2f}$).
- Backpan insulation thickness $T_{backpan}$.

Calculations:
1. Vision glass area: $A_{vision} = W_{bay} \cdot (H_{head} - H_{sill})$.
2. Spandrel opaque area: $A_{spandrel} = W_{bay} \cdot (H_{sill} + (H_{f2f} - H_{head}))$.
3. Total bay facade area: $A_{total} = A_{vision} + A_{spandrel} = W_{bay} \cdot H_{f2f}$.
4. Spandrel insulation volume: $V_{insul} = A_{spandrel} \cdot T_{backpan}$.
5. Perimeter slab firestop linear run: $L_{firestop} = W_{bay}$.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
