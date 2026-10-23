# Architecture Report: Source Floor Waste Drain & Pluvial Penetration Shadow Authority (v1)

## Executive Summary
Plumbing regulations (AS/NZS 3500.2 / IPC / UPC) require floor waste gullies (FWG), shower drains, and balcony rainwater outlets in wet and external areas.
Naive floor plan extraction ignores floor wastes or dismisses them as isolated text noise, causing:
1. Missing slab coring/sleeving penetrations through structural floor slabs.
2. Missing puddle flange membrane clamping collars and underside fire stop collars in multi-storey buildings.

This authority inventories floor wastes, resolves pipe diameters and slab coring penetration sizes, and flags puddle flange waterproofing collars and firestop assemblies in shadow candidate mode.

## Workstream Reference
- **Workstream B Item 19:** Plumbing fixtures, floor wastes, slab penetrations, and puddle flange details.

## Waste Drain & Penetration Model
Given:
- Drain kind: `FLOOR_WASTE_GULLY`, `FLOOR_WASTE_SHOWER`, `BALCONY_DECK_DRAIN`, `INSPECTION_OPENING`.
- Pipe nominal diameter $D_{pipe}$ (e.g. 50mm, 80mm, 100mm).

Calculations:
1. Slab penetration sleeve diameter: $D_{sleeve} = D_{pipe} + 25\text{ mm}$ (approx. $0.71\text{ pt}$ at 1:100 scale).
2. Puddle flange collar required for any drain embedded in a waterproofed slab.
3. Fire collar required if penetrating a fire-rated suspended slab.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
