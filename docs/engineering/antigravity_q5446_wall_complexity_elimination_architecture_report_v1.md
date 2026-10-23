# Architecture Report: Q5446 Physical-Wall Candidate Complexity Elimination (Item 21)

## Executive Summary
This document establishes the architecture for the **Q5446 Physical-Wall Candidate Complexity Elimination** via typed negative non-wall ink filtering in `pb_physical_wall_candidate_authority.py`, resolving Workstream C, Item 21 of the Autonomous Core Accuracy Engineering Mission: "Diagnose and eliminate the Q5446 physical-wall candidate complexity failure without weakening safety limits."

The primary blockers addressed are:
1. **Safety Cap Trip on Outlined Character Polylines:** In dense architectural plan drawings such as Q5446 Standard Plans V1 Page 1, annotations, specifications, and drawing schedules were drafted using vector-stroked font outlines (character glyphs drawn as 3–10 segment vector strokes) rather than embedded text fonts. On Page 1, this generated 47,184 raw line segments, exceeding the invariant 20,000 native primitive safety cap and triggering `PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED`.
2. **Preservation of Safety Limits:** Non-negotiable repository rules forbid raising the 20,000 primitive safety cap or bypassing the complexity ceiling. Weakening safety limits would degrade performance and risk memory exhaustion on arbitrarily large plan sets.
3. **Deterministic Negative Ink Disambiguation:** By analyzing glyph runs, repeated drafting character strokes, and non-wall vector ink while strictly safeguarding legitimate wall segments and explicitly preserved source primitive IDs, non-wall strokes are safely excluded before spatial candidate indexing. This drops the active segment count on Q5446 Page 1 from 41,932 down to 8,669 (a 79.3% reduction), safely resolving the complexity failure without weakening limits.

---

## Technical Architecture & Invariants

### 1. Root Cause Analysis
- Standard text rendering in vector PDFs either embeds fonts (producing TextPage spans) or converts glyphs into vector strokes (producing tens of thousands of tiny line segments).
- On Q5446 Page 1:
  - Total raw segments: 47,184.
  - Default drafting filter retained: 41,932 segments.
  - Maximum allowed threshold: 20,000 segments.
  - Result: pipeline halted with `scope_complete = False` and `PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED`.

### 2. Typed Negative Non-Wall Ink Filtering
- Added parameter `filter_typed_negative_non_wall_ink_shadow: bool = False` to `_filter_repeated_non_physical_drafting_primitives`, `filtered_wall_topology_source_segment_count`, `_assemble_scope_result`, and `_build_opening_local_supplemental_scope_result`.
- Enforces strict type contract: explicit boolean required (raises `TypeError` if non-boolean passed).
- Evaluates geometric characteristics of glyph strokes:
  - Segment length distribution typical of character strokes ($L \le 12.0$ pt).
  - Spatial grouping into character-like bounding clusters along text baselines.
  - Absence of parallel wall face pairing or continuous structural enclosure.
- Non-wall primitives identified by the negative filter are quarantined as `FilteredNativePrimitiveReceipt` with reason code `EXCLUDED_TYPED_NEGATIVE_NON_WALL_INK`.

### 3. Safeguards & Invariants
- **Preserved Primitive Protection:** Any primitive ID present in `preserved_source_primitive_ids` is unconditionally retained, even if it falls within a detected glyph run or non-wall ink cluster.
- **20,000 Safety Cap Unchanged:** The 20,000 segment limit remains strictly enforced. No thresholds were raised or weakened.
- **Customer Baseline Unchanged:** Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
- **Shadow Mode Entrypoint:** Exposed via `PhysicalWallCandidateProducer.from_source_visibility_typed_negative_wall_ink_shadow()`, ensuring zero interference with existing production pipelines until explicit authority enablement.

---

## Verification & Test Results
- Synthetic building + glyph run test verifies exact discrimination between structural walls and text glyphs (`test_synthetic_building_and_glyph_run_filtering`).
- Preserved primitive test verifies protected IDs survive filtering (`test_preserved_source_primitive_ids_never_filtered_even_if_in_negative_run`).
- Original Q5446 Page 1 verified:
  - Without filter: 41,932 segments (exceeds 20,000 cap).
  - With shadow filter: 8,669 segments (safely below 20,000 cap).
  - Scope complete with zero complexity failure codes.
- All 17 customer retention regression tests pass byte-for-byte.
