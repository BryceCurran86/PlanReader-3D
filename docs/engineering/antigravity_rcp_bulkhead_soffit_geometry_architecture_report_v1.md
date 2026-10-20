# Architecture Report: Source Reflected Ceiling Plan Bulkhead & Soffit Stepped Geometry Shadow Authority (v1)

## Executive Summary
Architectural reflected ceiling plans (RCPs) delineate multi-level ceiling designs incorporating bulkheads, coves, and dropped perimeter soffits.
Naive extraction treats each room as having a single flat horizontal ceiling at one nominal height. This failure mode:
1. Omits vertical bulkhead fascia surface areas ($\Delta H \cdot L_{step}$), creating severe plasterboard and paint under-takeoffs.
2. Misses ceiling clashes with tall doorways, curtain tracks, and high kitchen cabinetry.

This authority models multi-tiered ceiling zones within room perimeters, resolving the vertical step transition ($\Delta H = H_{high} - H_{low}$) and vertical fascia lining surface area ($A_{fascia}$) in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 16:** Reflected ceiling plan geometry, bulkheads, soffits, and ceiling finish takeoff.

## Stepped Ceiling Geometry Model
Given:
- Room perimeter $P_{room}$, high ceiling elevation $H_{high}$, dropped soffit elevation $H_{low}$ ($H_{low} < H_{high}$).
- Bulkhead transition edge length $L_{step}$ and dropped soffit polygon area $A_{soffit}$.

Calculations:
1. Vertical step drop: $\Delta H = H_{high} - H_{low}$.
2. Vertical fascia surface area: $A_{fascia} = L_{step} \cdot \Delta H$.
3. Total horizontal ceiling lining area: $A_{room}$.
4. Total combined ceiling finish area: $A_{total} = A_{room} + A_{fascia}$.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
