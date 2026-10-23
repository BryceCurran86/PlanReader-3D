# Architecture Report: Source External Balcony & Terrace Fall Slope Drainage Shadow Authority (v1)

## Executive Summary
External balconies, terraces, and podium decks are subjected to direct precipitation and require engineered drainage slopes (typically 1:100 or 1:80 falls) conforming to AS 4654 / NCC / IBC waterproofing standards.
Standard flat 2D extraction causes two severe quantity errors:
1. Omitting threshold step-down height clearances (minimum 50-100mm drop below internal FFL) critical for sliding door weathering and waterproofing hob design.
2. Estimating screed bedding as a uniform thin sheet, under-estimating topping screed concrete volume by 30% to 50% across sloping profiles.

This authority models external balcony drainage slopes, calculating the vertical fall ($\Delta H = L_{fall} / S$), threshold step-down, variable screed bedding volume ($V = A \cdot T_{avg}$), and linear strip drain lengths in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 18:** External balconies, terraces, fall slope drainage, and screed takeoff.

## Balcony Drainage & Screed Equations
Given:
- Balcony surface area $A$, drainage fall distance $L_{fall}$, slope ratio $1:S$ (e.g., $S = 100$).
- Minimum screed thickness at outlet $T_{min}$ (default 25mm / 0.71 pt).
- Doorway weather step-down $H_{step}$ (default 50mm / 1.42 pt).

Calculations:
1. Total vertical fall: $\Delta H_{fall} = \frac{L_{fall}}{S}$.
2. Maximum screed thickness at high point: $T_{max} = T_{min} + \Delta H_{fall}$.
3. Average screed thickness: $T_{avg} = T_{min} + \frac{\Delta H_{fall}}{2}$.
4. Sloping screed volume: $V_{screed} = A \cdot T_{avg}$.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
