# Architecture Report: Source Expansion & Control Joint Physical Discontinuity Shadow Authority (v1)

## Executive Summary
Large architectural structures and masonry facades incorporate planned expansion joints (EJ) and control joints (CJ) to accommodate thermal movement, foundation settlement, and concrete drying shrinkage.
Standard wall continuity engines encounter two failure modes at movement joints:
1. Erroneously bridging/healing across the intentional physical gap, generating false monolithic walls and suppressing structural isolation.
2. Mistaking the vertical wall gap for a door opening or pass-through void, artificially inflating opening schedules.

This authority identifies movement and control joints, enforces physical discontinuity across the joint gap ($W_{joint}$), suppresses false doorway formation, and calculates elastomeric sealant and backing rod linear takeoffs in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 4:** Physical wall continuity, movement joints, and intentional structural gaps.

## Joint Classification & Sealant Model
Given:
- Joint kind: `EXPANSION_JOINT`, `CONTROL_JOINT`, `CONSTRUCTION_JOINT`, `SEISMIC_ISOLATION_JOINT`.
- Gap width $W$, joint length $L$, sealant depth $D = \max(6\text{ mm}, W / 2)$.

Calculations:
1. Joint linear run: $L_{joint} = L$.
2. Sealant volume: $V_{sealant} = L \cdot W \cdot D$.
3. Physical constraints: `prohibits_wall_healing_stitching = True`, `is_doorway_opening = False`.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
