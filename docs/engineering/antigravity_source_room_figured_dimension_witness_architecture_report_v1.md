# Architecture Report: Source-Owned Room Figured Dimension and Wall Witness Shadow (Items 18 & 19)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream B, Items 18 & 19 ("Recover figured room dimensions and corresponding wall witnesses", "Produce trustworthy room-face evidence for GPT1 measurement").

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §5, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `pb_same_view_room_area_authority.py`
  - `pb_cross_view_room_area_authority.py`
  - `pb_source_room_face_authority.py`
  - `pb_raster_plan_dimension_authority.py`
  - `pb_gpt1_original_figured_face_witness_shadow.py`
  - `pb_gpt1_original_figured_extension_to_face_shadow.py`
  - `pb_source_rcp_ceiling_region_shadow.py`
  - `tests/test_same_view_room_area_authority_v1.py`
  - `tests/test_gpt1_lot16_original_wc_linen_dimension_witness.py`
  - `tests/test_gptmax_maryborough_room_first_owner_gate.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
- **Functions Traced:**
  - `pb_same_view_room_area_authority.SameViewRoomAreaProducer.publish` -> `_line_inside_dimension_pair` -> `_witness_systems_intersect` -> `first_failures["same_view_dimension_witness_intersection_unavailable"]`
  - `pb_source_room_face_authority._evaluate_face_ownership` -> `audit_source_room_face_owned_witnesses`
  - `pb_gpt1_original_figured_face_witness_shadow.source_figured_terminal_wall_faces_shadow`
- **Authority Boundaries Crossed:**
  - Begins strictly in **shadow mode** (`EvidenceResolutionStatus.CANDIDATE`).
  - `commercial_projection_allowed = False` and `takeoff_eligible = False`.
  - No existing signed quantity, fingerprint, or customer output is altered.
- **Untouched:**
  - `benchmarks/frozen_holdout/full_plan_v2/` (entire tree untouched).
  - 20,000 raster primitive cap and global 2.5 pt snapping tolerance untouched.
  - No baseline signed eight rows modified; byte-for-byte retention verified.

---

## 1. Observed Repository Behavior

1. **Current Room Dimension Gates:**
   - In `pb_same_view_room_area_authority.py` and `pb_cross_view_room_area_authority.py`, figured dimensions must pass `_witness_systems_intersect(horizontal, vertical)`.
   - `_witness_systems_intersect` requires that at least one witness segment from the horizontal dimension directly intersects (crosses) one witness segment from the vertical dimension within $10^{-6}$ pt tolerance.
   - If witness lines do not directly intersect (which is standard drafting practice when witness lines terminate at opposing wall faces rather than extending through the room corners), the authority falls back to `_dimension_is_immediate_label_annotation(line, dimension)`, failing with `same_view_dimension_witness_intersection_unavailable`.
2. **Current Room Face Boundaries:**
   - `pb_source_room_face_authority.py` produces `SourceRoomFaceRecord` and `audit_source_room_face_owned_witnesses`, establishing authenticated planar room polygons and their bounding wall IDs.
   - However, there is no producer-owned shadow module that directly verifies that a room polygon's internal wall faces correspond to the wall witness strokes of horizontal and vertical figured dimension chains.
3. **Downstream Measurement Need (GPT1):**
   - Downstream measurement lanes (GPT1, room finish mappers) require trustworthy, source-authenticated room-face evidence binding figured dimensions ($W_\text{mm} \times L_\text{mm}$) to the exact room internal faces and bounding walls, before any finish quantities (e.g. FT2/FT3 floor tiling, WFPB ceiling linings) can be safely projected.

---

## 2. Inference

- In architectural floor plans, dimension witness lines (extension lines) are drawn from internal wall faces to dimension rails.
- A horizontal dimension has witness lines extending from the left and right vertical wall faces of a room.
- A vertical dimension has witness lines extending from the top and bottom horizontal wall faces of a room.
- In CAD drafting, these witness lines often stop near the wall face (or at the dimension rail) and do not physically cross each other in the corners of the room.
- By verifying that the witness lines touch or are collinear extensions of the room polygon's internal wall edges (within drawing snap tolerance $\le 2.5\text{ pt}$), and that the figured millimeters match the geometric room span ratio within drawing scale tolerance, we can authenticate the figured room dimensions without requiring artificial intersecting witness extensions.
- When multiple conflicting dimension pairs match the same room face, the system must fail closed (`COMPETING_FIGURED_DIMENSION_PAIRS`), preserving precision over recall.

---

## 3. Proposed Change

Implement `pb_source_room_figured_dimension_witness_shadow.py`:
- **Selector:** `SourceRoomFiguredWitnessSelector` (document_id, revision_id, source_sha256, snapshot_id, page_id, physical_room_id, room_label).
- **Candidate Data Structures:**
  - `SourceBoundDimensionCandidate`: dimension_id, value_mm, orientation, endpoints_pt, witness_geometries, witness_observation_ids.
  - `SourceRoomFaceBoundaryEdge`: wall_id, role, start_pt, end_pt, stroke_id.
- **Evaluation Rules (Fail-Closed):**
  1. Validate exact document/revision/snapshot/source hash lineage.
  2. Validate room face polygon (must be simple, valid, finite non-zero area $\ge 3$ vertices).
  3. Separate dimension candidates into horizontal and vertical. Reject if either is missing (`DIMENSION_ORIENTATION_PAIR_UNAVAILABLE`).
  4. For each horizontal candidate:
     - Verify both terminals/witnesses align with opposing vertical room edges (left and right) within tolerance $\le 2.5\text{ pt}$.
     - Verify $W_\text{mm} > 0$ and is finite.
  5. For each vertical candidate:
     - Verify both terminals/witnesses align with opposing horizontal room edges (top and bottom) within tolerance $\le 2.5\text{ pt}$.
     - Verify $L_\text{mm} > 0$ and is finite.
  6. Verify scale consistency: $(W_\text{mm} / L_\text{mm})$ matches the geometric ratio $(W_\text{pt} / L_\text{pt})$ within allowable drawing tolerance (5%).
  7. Check uniqueness: if multiple pairs qualify $\to$ `COMPETING_FIGURED_DIMENSION_PAIRS`.
  8. Emit `SourceRoomFiguredWitnessRecord` with `status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- Benchmark truth values (e.g. Maryborough Laundry 8.34782 $\text{m}^2$, figured [1655, 5044], or Lot 16 room areas) are used solely as diagnostic observations and must NOT be hardcoded or used as selection thresholds or test oracles.
- The evaluation must apply identically across any architectural drawing set.

---

## 5. Required Test Matrix (`tests/test_source_room_figured_dimension_witness_shadow.py`)

1. **Positive synthetic test:** Complete rectangle room face with authentic horizontal and vertical witness lines matching wall faces.
2. **Negative - Missing orientation:** Only horizontal dimension provided $\to$ `DIMENSION_ORIENTATION_PAIR_UNAVAILABLE`.
3. **Negative - Unaligned witness lines:** Dimension witness lines offset away from room internal wall edges beyond tolerance $\to$ `WITNESS_WALL_ALIGNMENT_UNRESOLVED`.
4. **Negative - Scale inconsistent:** Figured values (e.g. $1000 \times 10000$) contradict room geometric aspect ratio ($1:1$) $\to$ `FIGURED_PAIR_SCALE_INCONSISTENT`.
5. **Conflict - Competing dimension pairs:** Two distinct valid dimension pairs for the same room $\to$ `COMPETING_FIGURED_DIMENSION_PAIRS`.
6. **Negative - Lineage mismatch:** Wrong document_id, revision_id, or source_sha256 $\to$ `SOURCE_LINEAGE_MISMATCH`.
7. **Negative - Invalid polygon:** Degenerate polygon $\to$ `INVALID_ROOM_POLYGON`.
8. **Metamorphic test:** Invariance under translation and rotation.
9. **No-mutation test:** Verify caller input data structures are not mutated.
10. **Customer retention test:** Verify byte-identical preservation of customer retention rows (`test_gptmax_original_eight_customer_retention.py`).
