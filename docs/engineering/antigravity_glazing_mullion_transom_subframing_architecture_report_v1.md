# Architecture Report: Source Glazing Mullion & Transom Sub-Framing Geometry Shadow Authority (v1)

## Executive Summary
Large architectural glazing installations (ribbon windows, curtain walls, storefronts) are partitioned into individual glass panes (lites) by intermediate vertical mullions and horizontal transoms. Treating such openings as monolithic glass plates results in:
1. Gross errors in glass procurement and pane dimension takeoff.
2. Inaccurate structural windload sizing (which depends on individual pane aspect ratio and area).
3. Complete omission of extruded aluminum/steel sub-framing linear meterage.

This authority models sub-framing topology, partitioning window apertures into bays and tiers, computing exact glass lite geometry, aspect ratios, mullion linear runs, and transom linear runs in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 10 / Workstream B Item 13:** Glazing sub-framing, mullion/transom geometry, and opening takeoff.

## Framing Equations & Partition Model
Given:
- Opening clear width $W$ and height $H$.
- Outer frame profile thickness $T_f$, intermediate mullion width $T_m$, intermediate transom height $T_t$.
- $N_m$ vertical mullions and $N_t$ horizontal transoms.

Calculations:
1. Number of glass lites: $N_{lites} = (N_m + 1) \cdot (N_t + 1)$.
2. Bay clear width: $w_{lite} = \frac{(W - 2 T_f) - N_m \cdot T_m}{N_m + 1}$.
3. Tier clear height: $h_{lite} = \frac{(H - 2 T_f) - N_t \cdot T_t}{N_t + 1}$.
4. Lite Area: $A_{lite} = w_{lite} \cdot h_{lite}$, Aspect Ratio = $w_{lite} / h_{lite}$.
5. Frame Linear Takeoffs:
   - Outer perimeter: $2 \cdot (W + H)$
   - Vertical mullions total length: $N_m \cdot (H - 2 T_f)$
   - Horizontal transoms total length: $N_t \cdot (W - 2 T_f)$

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
