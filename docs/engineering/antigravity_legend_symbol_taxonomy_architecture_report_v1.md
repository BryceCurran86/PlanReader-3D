# Architecture Report: Source Plan Legend Symbol Taxonomy & Graphical Key Disambiguation Shadow Authority (v1)

## Executive Summary
Architectural and engineering drawing sheets incorporate legend viewports and graphical key tables containing sample swatches (e.g., wall type cross-sections, electrical symbols, diffuser shapes) alongside descriptive text.
Naive 2D vector processors frequently ingest legend graphics as if they were situated inside the physical building floor plan, causing:
1. Spurious "ghost walls" created from wall hatch sample rectangles in the legend block.
2. Artificially inflated fixture counts (extra toilets, sinks, detectors, and switches) located outside building footprints.

This authority identifies legend and graphical key bounding envelopes, isolates legend primitives from plan space extraction, and translates sample swatches into an authoritative project symbol taxonomy in shadow candidate mode.

## Workstream Reference
- **Workstream C Item 26:** Legend recognition, graphical key taxonomy, and drawing viewport quarantine.

## Quarantine & Taxonomy Model
1. **Legend Viewport Envelope:**
   - Bounding box: $[x_{min}, y_{min}, x_{max}, y_{max}]$.
   - Primitives inside this envelope are marked `LEGEND_ANNOTATION_SWATCH` and quarantined from plan-space geometry engines.

2. **Symbol Taxonomy Extraction:**
   - Associates graphical symbol codes (e.g. `SD`, `FHR`, `GPO`, `W4`) with human-readable descriptions and discipline categories (`ELECTRICAL_SYMBOLS`, `FIRE_SERVICES`, `WALL_TYPES`, `PLUMBING_FIXTURES`, `MECHANICAL_HVAC`).

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
