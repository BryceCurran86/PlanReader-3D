# Antigravity Doorway Threshold Authentication and Transverse Wall Obstruction Report (v1)

## Compliance & Context

### Files Actually Read
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_source_open_passage_connection_shadow.py`
- `pb_source_floor_finish_occurrence_ownership_shadow.py`
- PR #3462 (shared coordination hub)
- PR #3455 (GPT2 architecture review)

### Exact Functions Traced
- `pb_source_open_passage_connection_shadow._segment_intersects_passage`: Lines 154–182
- `pb_source_open_passage_connection_shadow.evaluate_source_open_passage_connection_shadow`: Lines 185–344
- `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow`: Lines 224–377

### Authority Boundaries Crossed
- Geometry intersection testing (collinear vs transverse segment-segment intersection).
- Floor finish threshold spatial boundary alignment verification.
- Non-publishing shadow boundary: all results maintain `commercial_projection_allowed = False` and `takeoff_eligible = False`.

### Expected Abstentions Before Any Tests
- Any wall segment that crosses or intersects the passage line transverse-wise triggers `OPEN_PASSAGE_OBSTRUCTED_BY_WALL`, returning `EvidenceResolutionStatus.ABSTAINED`.
- Any floor finish occurrence with doorway thresholds that do NOT lie on or span the room boundary polygon will NOT authenticate doorway transition (`doorway_transition_authenticated = False`), or will abstain if threshold consistency is required.
- Retention of all existing customer bodies: zero impact on baseline fingerprints.

### Files That Will Remain Untouched
- All benchmark gold and holdout definitions (`benchmarks/**`).
- All production commercial extractors (`pb_planreader_pdf_extractor.py`, `pb_opening_production_v175.py`).
- Safety caps (20,000 primitives) and snap tolerance (2.5 pt).

---

## 1. Observed Repository Behavior

1. **`pb_source_open_passage_connection_shadow._segment_intersects_passage`**:
   The existing implementation projects segment endpoints `seg_start` and `seg_end` onto the passage vector:
   ```python
   a1, perp1 = proj(seg_start)
   a2, perp2 = proj(seg_end)
   if perp1 <= tolerance_pt and perp2 <= tolerance_pt:
       overlap = min(max(a1, a2), p_len) - max(min(a1, a2), 0.0)
       if overlap > tolerance_pt:
           return True
   return False
   ```
   This only flags a wall as obstructing the passage if the wall is *collinear* with the passage (`perp1 <= tolerance_pt and perp2 <= tolerance_pt`).
   If a physical wall segment crosses through the passage transversally (perpendicularly at 90°, diagonally at 45°, etc.), `perp1` and `perp2` are non-zero, so the function returns `False`. The open passage evaluator incorrectly treats the passage as unobstructed.

2. **`pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow`**:
   The existing code evaluates doorway transitions as:
   ```python
   # 5. Check doorway threshold transitions
   doorway_authenticated = False
   if doorway_transitions:
       doorway_authenticated = True
   ```
   It accepts any `SourceDoorwayThreshold` object supplied in `doorway_transitions` without checking whether the threshold line segment actually touches, aligns with, or spans an opening chord on the room's `internal_face_polygon_pdf_pts`. A distant threshold from another room or another sheet erroneously marks `doorway_transition_authenticated = True`.

---

## 2. Inference

1. A genuine open passage between two rooms must be free of any intersecting physical wall segments, whether collinear or transverse. Transverse segment-segment intersection must be calculated using robust 2D orientation / cross-product tests with snap tolerance.
2. A doorway transition for a floor finish is only valid if both endpoints of the doorway threshold lie within tolerance of the room perimeter boundary (or span a gap between boundary vertices). If no threshold aligns with the room polygon boundary, `doorway_transition_authenticated` must remain `False`.

---

## 3. Proposed Change

1. **In `pb_source_open_passage_connection_shadow.py`**:
   - Enhance `_segment_intersects_passage` to test both:
     a) Collinear overlap (existing logic).
     b) Transverse line segment intersection: using 2D orientation/cross-product tests between segment $(S_1, S_2)$ and passage $(P_1, P_2)$.
     c) If either condition holds, return `True` (passage is obstructed).

2. **In `pb_source_floor_finish_occurrence_ownership_shadow.py`**:
   - Add geometric boundary alignment helper `_threshold_aligns_with_polygon_boundary(threshold, poly_pts, tolerance_pt)`:
     Verifies that each endpoint of the threshold lies within `snap_tolerance_pt` of a polygon edge or vertex.
   - Update `evaluate_source_floor_finish_ownership_shadow` to only set `doorway_transition_authenticated = True` if at least one provided doorway threshold geometrically aligns with the room's boundary polygon.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- Maryborough architectural PDF `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007` contains FT2 (ceramic tiles) and FT3 (vinyl) transitions across doors D07–D13 and passages.
- Specific room names (OFFICE, FREEZER, LAUNDRY, etc.) or benchmark expected quantities must never be hardcoded into the algorithm.
- The logic must be purely geometric and fail-closed across all drawings.
