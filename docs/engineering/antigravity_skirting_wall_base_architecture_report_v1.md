# Architecture Report: Source Skirting Board & Wall Base Finish Linear Takeoff Shadow Authority (v1)

## Executive Summary
Architectural room finishes specify wall base trims (e.g., 67x18mm MDF bevelled skirtings, 100mm vinyl coving, or shadowline reveals) running along internal perimeter wall bases.
Standard quantity takeoff algorithms use raw room polygon perimeters ($P_{gross}$), introducing major procurement over-estimates:
1. Failing to deduct doorway openings ($\sum W_{door}$), where skirting stops at architraves and jambs.
2. Failing to deduct built-in joinery contact faces ($\sum L_{joinery}$), such as kitchen base cabinetry and built-in wardrobes that sit directly against bare plasterboard.

This authority computes net linear skirting runs per room ($L_{net} = P_{gross} - \sum W_{door} - \sum L_{joinery}$), isolates internal vs external corner mitre cuts, and categorizes profile specifications in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 20:** Room wall base trim, skirting deductions, and joinery contact takeoff.

## Linear Skirting Equations
Given:
- Room boundary gross perimeter $P_{gross}$.
- Doorway clear opening widths $\sum W_{door}$.
- Built-in joinery contact face lengths $\sum L_{joinery}$.

Calculations:
1. Net skirting linear run:
   $$L_{net} = \max(0, P_{gross} - \sum W_{door} - \sum L_{joinery})$$
2. Corner counts: $N_{int}$ internal mitres and $N_{ext}$ external mitres.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
