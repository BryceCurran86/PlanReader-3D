# Architecture Report: Source Floor Finish Occurrence and Physical Floor Ownership Shadow Authority (Item 14)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream B, Item 14 ("Resolve FT2 and FT3 drawing occurrences and exact physical floor ownership") and Construction Rule: "floor finishes terminate at internal wall faces, not beneath walls. Changes between carpet, tiles, vinyl or other finishes occur at the physical doorway or entrance transition shown on the drawings."

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `docs/engineering/GPT2_MARY_ORIGINAL_FINISH_CEILING_SOURCE_AUDIT_20261020.md`
  - `tools/diag_original_finish_mark_in_room_ink_shadow.py`
  - `tests/test_gpt2_native_ft2_ft3_original_mark_census.py`
  - `tests/test_gpt2_original_ft2_ft3_mark_ink_enclosure.py`
  - `tests/test_gpt2_ft2_internal_wall_face_basis.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
- **Functions Traced:**
  - `tools.diag_original_finish_mark_in_room_ink_shadow._native_mark_containment_census`
  - `tools.diag_original_finish_mark_in_room_ink_shadow.audit_original_floor_finish_mark_enclosure_candidate`
  - `tools.diag_original_finish_mark_in_room_ink_shadow.audit_competing_original_finish_mark_ownership`
  - `tools.diag_gpt2_original_figured_face_rivals_shadow.audit_original_ft2_internal_wall_face_basis`
- **Authority Boundaries Crossed:**
  - Strictly **shadow mode** (`EvidenceResolutionStatus.CANDIDATE`).
  - `commercial_projection_allowed = False` and `takeoff_eligible = False`.
  - Never invents wall lengths, heights, room areas, or physical floor finish identities.
  - No existing signed quantity, fingerprint, or customer output is altered.
- **Untouched:**
  - `benchmarks/frozen_holdout/full_plan_v2/` (entire tree untouched).
  - 20,000 raster primitive cap and global 2.5 pt snapping tolerance untouched.
  - Baseline signed eight rows byte-for-byte retention verified.

---

## 1. Observed Repository Behavior

1. **Floor Finish Census vs Ownership Gap:**
   - Previous diagnostics (`tools/diag_gpt2_source_schedule_occurrence_census.py` and `tools/gpt2_native_material_mark_census.py`) successfully censused native words for material codes FT2 and FT3 (8 FT2 and 5 FT3 on Maryborough plan view).
   - However, in `tools/diag_original_finish_mark_in_room_ink_shadow.py`, `physical_source_floor_owner_authenticated` was explicitly left as `False` because no authority module proved that the mark was contained in an authenticated room boundary, terminated at internal wall faces, and verified absence of competing finish codes.
2. **Construction Rule Requirements:**
   - "floor finishes terminate at internal wall faces, not beneath walls. Changes between carpet, tiles, vinyl or other finishes occur at the physical doorway or entrance transition shown on the drawings."
   - Prior code lacked explicit geometry checks verifying that the finish polygon does not cross beneath bounding walls or bleed across door thresholds without transition strokes.

---

## 2. Inference

- An authenticated floor finish occurrence requires:
  1. A unique, valid native material mark occurrence (e.g. FT2, FT3) located inside the room polygon with a safe boundary clearance ($\ge 2.5$ pt).
  2. Proof that no competing mark of a different material code (e.g. FT2 inside an FT3 space) or unproven duplicate mark exists within the same physical space.
  3. Geometric verification that the finish boundary terminates strictly at internal wall faces and doorway threshold transition strokes, excluding wall footprints beneath walls.

---

## 3. Proposed Change

Implement `pb_source_floor_finish_occurrence_ownership_shadow.py`:
- **Selector:** `SourceFloorFinishOwnershipSelector` (document_id, revision_id, source_sha256, snapshot_id, page_id, room_id, material_code).
- **Data Structures:**
  - `SourceFloorFinishMark`: occurrence_id, page_id, material_code, mark_center_pt, source_word_address.
  - `SourceDoorwayThreshold`: threshold_id, start_pt, end_pt.
  - `SourceFloorFinishOwnershipRecord`: record_id, selector, finish_boundary_polygon_pdf_pts, internal_area_sq_pt, terminates_at_internal_faces=True, under_wall_finish_excluded=True, doorway_transition_authenticated=True.
  - `SourceFloorFinishOwnershipResult`: status, reason_codes, record, selector.
- **Evaluation Rules (Fail-Closed):**
  1. Validate exact lineage (doc, rev, SHA256 64-hex, snapshot, page, room, code).
  2. Validate polygon validity and calculate internal floor area.
  3. Validate mark enclosure:
     - Mark center must be strictly inside polygon.
     - Distance to polygon edges must be $\ge$ clearance tolerance ($\ge 2.5$ pt).
  4. Validate uniqueness:
     - Check `other_finish_marks`. If any mark with a different material code is inside polygon $\to$ `COMPETING_FINISH_CODES_IN_ROOM`.
     - If duplicate mark with same code is inside polygon $\to$ `COMPETING_FINISH_MARKS_IN_ROOM`.
  5. Validate construction rule:
     - Polygon edges must match internal wall faces or doorway threshold chords.
     - Wall footprint exclusion verified.
  6. Emit `SourceFloorFinishOwnershipRecord` with `status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- References to FT2, FT3, Maryborough, PWD, or OFFICE are illustrative only.
- The algorithm evaluates general polygon-edge, point-in-polygon, and threshold-chord relationships deterministically without project-specific hardcoding.

---

## 5. Required Test Matrix (`tests/test_source_floor_finish_occurrence_ownership_shadow.py`)

1. **Positive - Authentic FT2/FT3 floor finish ownership:** Valid room with internal wall faces, doorway threshold, and enclosed FT2/FT3 mark.
2. **Negative - Mark outside room polygon:** Mark center outside polygon $\to$ `MARK_NOT_IN_ROOM_POLYGON`.
3. **Negative - Mark too close to wall face:** Mark center within $< 2.5$ pt of wall edge $\to$ `MARK_TOO_CLOSE_TO_WALL_FACE`.
4. **Conflict - Competing finish codes:** An FT2 and FT3 mark inside the same room polygon $\to$ `COMPETING_FINISH_CODES_IN_ROOM`.
5. **Conflict - Duplicate same-code marks:** Two distinct marks of same code without multi-bay zoning $\to$ `COMPETING_FINISH_MARKS_IN_ROOM`.
6. **Negative - Material code mismatch:** Selector code differs from mark code $\to$ `FINISH_MATERIAL_CODE_MISMATCH`.
7. **Negative - Invalid polygon:** Degenerate or non-simple polygon $\to$ `INVALID_ROOM_POLYGON`.
8. **Negative - Lineage mismatch:** Bad SHA-256 or empty fields $\to$ `SOURCE_LINEAGE_MISMATCH`.
9. **Metamorphic test:** Invariance under translation.
10. **No-mutation test:** Verify caller input data structures are not mutated.
11. **Customer retention test:** Verify byte-identical preservation of customer retention rows.
