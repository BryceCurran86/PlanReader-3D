# Architecture Report: Source Typed Negative Evidence Structural Filtering Shadow Authority (v1)

## Executive Summary
In architectural PDF vector extraction, annotation artifacts such as dimension witness lines, extension ticks, structural grid lines, casework/joinery boundaries, and furniture contours frequently mimic or intersect structural wall strokes. Previous naive heuristics either mistakenly promoted thin annotation strokes into partition walls, or prematurely and destructively deleted real wall segments that intersected dimension or grid lines.

This authority codifies typed opposing negative evidence atoms without destructive early deletion, preserving candidate wall segments through topological evaluation while scoring opposing annotations.

## Workstream & Playbook Reference
- **Workstream C Item 28:** Typed negative evidence codification for structural walls.
- **Engineering Playbook §13 Priority 3:** Non-destructive negative evidence accumulation.

## Architecture & Subsystems
1. **NegativeEvidenceKind Classification:**
   - `DIMENSION_WITNESS_LINE`: Thin stroke collinear or terminating at dimension text/arrowhead.
   - `DIMENSION_TICK`: Short oblique or perpendicular tick (length <= 15 pt).
   - `GRID_LINE`: Centerline spanning across exterior building boundaries or terminating at grid bubbles.
   - `FURNITURE_LOOP`: Closed loop or curved polyline belonging to loose equipment or sanitary fixtures.
   - `JOINERY_BOUNDARY`: Thin casework outline, counter edge, or overhead dashed cabinet line.
   - `GLAZING_MULLION_OR_SILL`: Thin line situated within a confirmed opening frame/aperture.

2. **Negative Evidence Evaluation Model:**
   - Rather than dropping primitives immediately, the authority generates immutable `NegativeEvidenceAtom` records.
   - A candidate wall segment is evaluated against intersecting or collinear negative evidence atoms.
   - If a candidate segment has strong positive structural evidence (e.g. width >= 2.0 pt, solid fill, parallel boundary corroboration), negative evidence is logged but structural candidacy is preserved.
   - If a candidate segment lacks structural corroboration and matches negative evidence criteria (e.g. thin stroke width <= 0.35 pt collinear with dimension string), it is disqualified with `DISQUALIFIED_BY_NEGATIVE_EVIDENCE`.

3. **Invariants & Safety:**
   - Candidate shadow mode only (`EvidenceResolutionStatus.CANDIDATE`).
   - `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Preserves global 2.5 pt snap tolerance.
   - Preserves 20,000 primitive safety cap.
   - Zero benchmark gold dependencies.
