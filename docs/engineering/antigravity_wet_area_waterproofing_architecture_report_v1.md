# Architecture Report: Source Wet Area Waterproofing Membrane & Wall Upstand Height Shadow Authority (v1)

## Executive Summary
In residential and commercial buildings, wet areas (bathrooms, ensuites, laundries, powder rooms, commercial kitchens) mandate continuous waterproof membranes complying with AS 3740 / NCC / IBC codes.
Standard flooring takeoffs only measure the horizontal 2D room floor polygon. This limitation:
1. Ignores vertical perimeter wall upstands (e.g., 150mm skirtings) and full-height shower wall tanking (e.g., 2000mm behind shower heads).
2. Severely underestimates membrane materials (liquid polyurethane, sheet membranes, reinforcing bandaging) by 25% to 50% depending on bathroom geometry.

This authority integrates wet area classification, shower recess identification, perimeter wall upstands, and shower wall tanking to resolve comprehensive 3D waterproofing membrane surface areas in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 15:** Wet area waterproofing, shower wall tanking, and finish takeoff.

## Waterproofing Surface Equations
Given:
- Wet area floor area $A_{floor}$.
- General wall perimeter $P_{gen}$ and general upstand height $H_{gen}$ (default 150mm).
- Shower wall perimeter $P_{shower}$ and shower wall tanking height $H_{shower}$ (default 2000mm).

Calculations:
1. General wall upstand area: $A_{gen\_upstand} = P_{gen} \cdot H_{gen}$.
2. Shower wall tanking area: $A_{shower\_tank} = P_{shower} \cdot H_{shower}$.
3. Total vertical upstand area: $A_{vertical} = A_{gen\_upstand} + A_{shower\_tank}$.
4. Total waterproofing membrane area: $A_{total} = A_{floor} + A_{vertical}$.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
