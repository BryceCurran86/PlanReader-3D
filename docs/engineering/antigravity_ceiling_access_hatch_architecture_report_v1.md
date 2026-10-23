# Architecture Report: Source Ceiling Access Hatch & Attic Inspection Trapdoor Geometry Shadow Authority (v1)

## Executive Summary
Reflected ceiling plans delineate utility access hatches and inspection trapdoors providing maintenance entry to roof trusses, HVAC equipment, and hydraulic service plenums.
Naive ceiling extraction produces two common errors:
1. Omitting access panel hardware items and perimeter frame trim from cost schedules.
2. Mistakenly classifying the 600x600mm hatch bounding box as a micro-room, polluting room schedule metrics.

This authority inventories ceiling access hatches, calculates opening dimensions, checks minimum code accessibility compliance ($\ge 450 \times 450\text{ mm}$), evaluates perimeter trim framing ($2(W + L)$), and binds fire resistance performance ratings in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 17:** Ceiling fixtures, access panels, penetration trims, and finish takeoff.

## Hatch Geometry & Performance Model
Given:
- Clear aperture width $W$ and length $L$.
- Fire rating: `NON_RATED`, `FIRE_RATED_30_MIN`, `FIRE_RATED_60_MIN`, `FIRE_RATED_120_MIN`.

Calculations:
1. Panel face area: $A = W \cdot L$.
2. Frame trim perimeter: $P = 2 \cdot (W + L)$.
3. Compliance check: $W \ge W_{min}$ and $L \ge L_{min}$ (default 450mm / 12.75 pt at 1:100 scale).

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
