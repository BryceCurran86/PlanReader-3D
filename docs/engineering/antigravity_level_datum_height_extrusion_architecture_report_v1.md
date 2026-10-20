# Architecture Report: Source Multi-Story Floor-to-Floor Level Datum & Height Extrusion Shadow Authority (v1)

## Executive Summary
Multi-story building documentation defines 3D vertical geometry using section and elevation Reduced Level (RL) datums (e.g., Ground RL +10.00m, Level 1 RL +13.50m, Level 2 RL +16.80m).
Naive 2D plan extraction reads each floor plan sheet in isolation and applies a hardcoded uniform height (e.g., 2.7m), resulting in:
1. Significant distortion of inter-story structural elements (columns, core shear walls, stair rises).
2. Failure to account for variable story heights (e.g., 4.5m ground floor retail vs 3.3m typical residential levels).
3. Incorrect total building height and facade envelope takeoffs.

This authority reconciles building level datums into an ordered vertical story stack, computing exact floor-to-floor heights ($\Delta H = RL_{i+1} - RL_i$) and associating plan sheets with verified 3D extrusion intervals in shadow candidate mode.

## Workstream Reference
- **Workstream C Item 25:** Multi-sheet elevation datums, level schedules, and 3D extrusion bounds.

## Story Level Mathematical Model
Given:
- An ordered set of $N$ building levels: $RL_0 < RL_1 < \dots < RL_{N-1}$.

Calculations:
1. Floor-to-floor height for story $i$ ($0 \le i < N-1$):
   $$H_{f2f, i} = RL_{i+1} - RL_i$$
2. Total building vertical height:
   $$H_{building} = RL_{N-1} - RL_0$$
3. Finished floor level (FFL) and structural slab level (SSL) offset:
   $$SSL_i = FFL_i - T_{finish}$$

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
