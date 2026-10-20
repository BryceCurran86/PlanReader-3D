# Architecture Report: Source-Owned Room Boundary Doorway Opening Shadow Authority (Items 11 & 13)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream B, Item 11 ("Complete OFFICE, FREEZER, WASH UP and FOOD PREP physical boundaries"), Item 13 ("Complete LAUNDRY, AIRLOCK, PWD, M-AMB and F-AMB"), and Workstream A, Item 7 ("Resolve wall openings without incorrectly splitting continuous walls") and Item 10 ("Recover closed, physically meaningful room boundaries without inventing partitions").

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `pb_source_room_face_authority.py`
  - `tools/diag_gptmax_maryborough_room_first_owner_gate.py`
  - `tests/test_gptmax_maryborough_room_first_owner_gate.py`
  - `tests/test_gpt2_original_ambulant_d11_d12_separate_door_ink.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
- **Functions Traced:**
  - `pb_source_room_face_authority._evaluate_face_ownership` -> `_containing_wall_ids` -> `SourceRoomFaceEdgeOwnershipFinding(kind=EDGE_OWNERSHIP_NONE)` -> `source_room_face_edge_owner_missing` -> `SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED`
  - `tools/diag_gptmax_maryborough_room_first_owner_gate.source_withheld_boundary_w4_census`
- **Authority Boundaries Crossed:**
  - Strictly **shadow mode** (`EvidenceResolutionStatus.CANDIDATE`).
  - `commercial_projection_allowed = False` and `takeoff_eligible = False`.
  - Never invents wall lengths, heights, room areas, or physical wall identities.
  - No existing signed quantity, fingerprint, or customer output is altered.
- **Untouched:**
  - `benchmarks/frozen_holdout/full_plan_v2/` (entire tree untouched).
  - 20,000 raster primitive cap and global 2.5 pt snapping tolerance untouched.
  - Baseline signed eight rows byte-for-byte retention verified.

---

## 1. Observed Repository Behavior

1. **Root Cause of Withheld Room Boundaries:**
   - In `pb_source_room_face_authority.py` (`_evaluate_face_ownership`), every edge of a planar room polygon is checked against `wall_edges` via `_containing_wall_ids`.
   - Architectural rooms almost universally possess doorways or entrances (e.g. LAUNDRY has door D10, F-AMB has D11, M-AMB has D12, PWD has D13, AIRLOCK has D08/D09, OFFICE has D07).
   - At a doorway, the physical wall candidate is interrupted by the door opening void. Consequently, the polygon edge spanning the doorway has NO containing wall in `wall_edges`.
   - `pb_source_room_face_authority.py` treats any edge without a wall as `EDGE_OWNERSHIP_NONE`, tagging the edge as `source_room_face_edge_owner_missing`.
   - Because of this, the entire face is marked `source_room_face_boundary_unresolved` and withheld into `abstained_faces`.
2. **Current First-Gate Census:**
   - In `tools/diag_gptmax_maryborough_room_first_owner_gate.py`, `source_withheld_boundary_w4_census` inspects precisely these withheld faces where `face.reason == "source_room_face_boundary_unresolved"`.
   - These rooms possess authentic wall candidate boundaries on 3 or 4 sides, but fail complete closure solely due to the unauthenticated doorway opening chord.

---

## 2. Inference

- A doorway chord is a physical opening void, not a missing wall defect.
- In architectural construction, room boundaries consist of internal wall faces plus doorway threshold lines.
- By providing a producer-owned shadow authority that verifies that every non-wall edge of a room face matches an authenticated opening void (spanning between structural wall jamb endpoints within $\le 2.5$ pt tolerance), the room boundary achieves complete topological closure without inventing artificial partitions.
- If an unowned edge does not correspond to an authentic opening candidate, the room boundary must continue to fail closed (`ROOM_BOUNDARY_DEFECT_REMAINS`).

---

## 3. Proposed Change

Implement `pb_source_room_boundary_doorway_opening_shadow.py`:
- **Selector:** `SourceRoomDoorwayOpeningSelector` (document_id, revision_id, source_sha256, snapshot_id, page_id, room_id, room_label).
- **Inputs:**
  - `withheld_face_polygon_pdf_pts`: polygon vertices of the candidate room face.
  - `wall_edges`: tuple of authenticated `(wall_id, edge)` wall boundary segments.
  - `opening_candidates`: tuple of authenticated door/window opening voids with their chord endpoints and opening IDs.
- **Evaluation Rules (Fail-Closed):**
  1. Validate exact document/revision/snapshot/source SHA lineage.
  2. Validate polygon validity (simple, non-zero finite area).
  3. For each edge of the polygon:
     - Check if contained by an authentic wall in `wall_edges` $\to$ `EDGE_STATUS_WALL_OWNED`.
     - Else, check if aligned with an authenticated opening candidate chord in `opening_candidates` within snap tolerance $\le 2.5$ pt $\to$ `EDGE_STATUS_DOORWAY_OPENING_AUTHENTICATED`.
     - If neither $\to$ `EDGE_STATUS_UNOWNED_DEFECT`.
  4. Require that 100% of polygon edges are accounted for (wall-owned or doorway-opening-authenticated). If any unowned edge remains $\to$ fail closed: `ROOM_BOUNDARY_DEFECT_REMAINS`.
  5. Check uniqueness: if multiple competing openings claim the same doorway chord $\to$ `COMPETING_OPENING_CHORD_OWNERSHIP`.
  6. Emit `SourceRoomBoundaryDoorwayRecord` with `status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- References to specific doors (D10, D11, D12, etc.) or rooms are illustrative only.
- The algorithm evaluates general polygon-edge to wall/opening relationships deterministically and holds no project-specific thresholds or shortcuts.

---

## 5. Required Test Matrix (`tests/test_source_room_boundary_doorway_opening_shadow.py`)

1. **Positive - Room with doorway opening:** Rectangular room with 3 solid walls and 1 doorway opening in the 4th wall, verified as a closed room boundary.
2. **Negative - Unaccounted gap/defect:** A gap in the wall network without an authentic opening candidate $\to$ `ROOM_BOUNDARY_DEFECT_REMAINS`.
3. **Negative - Misaligned opening chord:** Opening chord offset beyond 2.5 pt tolerance $\to$ `ROOM_BOUNDARY_DEFECT_REMAINS`.
4. **Conflict - Competing opening candidates:** Multiple distinct opening candidates claiming the same doorway chord $\to$ `COMPETING_OPENING_CHORD_OWNERSHIP`.
5. **Negative - Invalid polygon:** Degenerate or non-simple polygon $\to$ `INVALID_ROOM_POLYGON`.
6. **Negative - Lineage mismatch:** Invalid SHA-256 or empty fields $\to$ `SOURCE_LINEAGE_MISMATCH`.
7. **Metamorphic test:** Invariance under translation and rotation.
8. **No-mutation test:** Verify caller input data structures are not mutated.
9. **Customer retention test:** Verify byte-identical preservation of customer retention rows.
