# Architecture Report: Source Wall Acoustic Insulation Batt Infill Shadow Authority (v1)

## Executive Summary
Architectural partition schedules and acoustic engineering reports specify internal cavity acoustic batts (e.g. Bradford Soundscreen, Rockwool, R2.5 high-density batts) installed inside stud partition frames.
Naive wall quantity takeoff only computes gross wall surface area ($L \cdot H$). This causes two critical errors:
1. Omitting door and window aperture deductions, leading to material waste over-estimates of 15% to 30%.
2. Treating all walls uniformly, failing to isolate acoustically rated partitions (e.g., separating walls, bathroom perimeters) from un-insulated standard partitions.

This authority reconciles acoustic partition types, stud cavity thicknesses, opening deductions, and acoustic performance ratings (Rw, R-value) to calculate net insulation area ($m^2$) and volume ($m^3$) in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 6:** Wall partition types, acoustic schedules, and cavity insulation infill.

## Acoustic Takeoff Equations
Given:
- Wall length $L$ and height $H$.
- Opening void deductions $A_{openings} = \sum (w_i \cdot h_i)$.
- Stud cavity depth $T_{cavity}$.

Calculations:
1. Gross wall area: $A_{gross} = L \cdot H$.
2. Net acoustic insulation batt area: $A_{net} = \max(0, A_{gross} - A_{openings})$.
3. Batt insulation volume: $V_{batt} = A_{net} \cdot T_{cavity}$.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
