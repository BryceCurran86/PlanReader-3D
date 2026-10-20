# Architecture Report: Source-Owned Open Passage and Connected Space Shadow Authority (Items 12 & 20)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream B, Item 12 ("Recover FOOD SERVICE/POS COUNTER and their actual open connections"), Item 20 ("Preserve genuine open passages; never invent partitions just to close a polygon"), and Workstream A, Item 10 ("Recover closed, physically meaningful room boundaries without inventing partitions").

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `docs/engineering/GPT2_MARY_SOURCE_EDGE_RING_ABSTAIN_20261020.md`
  - `tools/diag_gpt2_source_room_cycle_shadow.py`
  - `pb_source_room_face_authority.py`
  - `pb_gpt1_figured_open_plan_sections_shadow.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
- **Functions Traced:**
  - `tools/diag_gpt2_source_room_cycle_shadow.audit_source_ring` -> `open_passage_or_branch_endpoint_degree_not_two`
  - `pb_source_room_face_authority._evaluate_face_ownership` -> `SOURCE_ROOM_FACE_EDGE_OWNER_MISSING`
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

1. **Cycle Requirement Leading to Artificial Partitions:**
   - In `tools/diag_gpt2_source_room_cycle_shadow.py`, candidate room boundaries are checked for simple geometric loops where every vertex has an endpoint degree of exactly two.
   - When rooms have genuine open passages (such as WASH UP connecting to FOOD PREP, or FOOD SERVICE opening into POS COUNTER), the absence of a closing wall leaves endpoint degree $\ne 2$, returning `open_passage_or_branch_endpoint_degree_not_two`.
   - In naive heuristic approaches, systems would inject an imaginary partition or divider wall across the gap just to close the polygon, violating architectural reality and creating false physical walls.
2. **Construction Rule on Floor Finishes:**
   - The mission explicitly establishes: "floor finishes terminate at internal wall faces, not beneath walls. Changes between carpet, tiles, vinyl or other finishes occur at the physical doorway or entrance transition shown on the drawings."
   - Where adjoining rooms share the identical finish specification (e.g. both Food Prep and Wash Up having FT3 tile), the finish flows continuously through the open passage without requiring a divider wall.
   - Where finishes differ, the transition occurs at an authenticated threshold transition mark.
   - If finishes differ and no transition mark exists, the system must fail closed (`UNPARTITIONED_FINISH_CONFLICT`) rather than guessing a boundary.

---

## 2. Inference

- An open passage is a legitimate architectural feature: a throat between two authenticated wall termination jambs where no structural wall exists.
- In commercial service areas (e.g. Maryborough FOOD SERVICE and POS COUNTER), the physical reality is an open connected space with counter fixtures, not four-walled enclosures.
- By representing open passages as topological portals between adjoining spaces:
  1. We prove that the passage is framed by authentic structural wall ends.
  2. We verify that no physical wall stands in the passage opening.
  3. We authenticate whether the floor finish flows continuously (identical finish codes) or transitions at an authenticated doorway threshold line.
  4. We prevent artificial wall fabrication while enabling downstream measurement of unified finish zones.

---

## 3. Proposed Change

Implement `pb_source_open_passage_connection_shadow.py`:
- **Selector:** `SourceOpenPassageSelector` (document_id, revision_id, source_sha256, snapshot_id, page_id, primary_room_id, connected_room_id).
- **Inputs:**
  - `passage_endpoints`: pair of wall termination points framing the opening.
  - `primary_wall_edges` & `connected_wall_edges`: authentic boundary wall edges.
  - `transition_mark_geometry`: optional threshold/transition line stroke.
  - `primary_finish_code` & `connected_finish_code`: finish materials of adjoining rooms.
  - `existing_wall_candidates`: to verify no wall obstructs the passage.
- **Evaluation Rules (Fail-Closed):**
  1. Validate exact document/revision/snapshot/source SHA lineage.
  2. Verify passage endpoints align with actual wall terminations within snap tolerance $\le 2.5$ pt.
  3. Verify clear width is positive and non-zero ($w_\text{pt} > 0$).
  4. Verify no structural wall candidate stands across the opening (`OPEN_PASSAGE_OBSTRUCTED_BY_WALL`).
  5. Check finish semantics:
     - If transition stroke exists $\to$ `physical_transition_stroke`.
     - Else if finish codes match $\to$ `contiguous_finish_flow`.
     - Else (differing finish codes without transition stroke) $\to$ fail closed: `UNPARTITIONED_FINISH_CONFLICT`.
  6. Emit `SourceOpenPassageRecord` with `partition_invented = False`, `status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- Observations regarding specific room names (e.g. Maryborough Food Service or Wash Up) are used for architectural context only.
- The algorithm applies generally to any open passage or connected space across any architectural plan set. No benchmark quantities, thresholds, or project-specific hacks are used.

---

## 5. Required Test Matrix (`tests/test_source_open_passage_connection_shadow.py`)

1. **Positive - Physical transition stroke:** Adjoining rooms with differing finishes (e.g. FT2 and carpet) connected by an open passage with an authentic threshold transition mark.
2. **Positive - Contiguous finish flow:** Adjoining rooms sharing identical finish code (e.g. FT3 and FT3) with seamless open passage.
3. **Negative - Unpartitioned finish conflict:** Differing finish codes without a transition stroke $\to$ `UNPARTITIONED_FINISH_CONFLICT`.
4. **Negative - Obstructed by wall:** A physical wall candidate exists across the passage $\to$ `OPEN_PASSAGE_OBSTRUCTED_BY_WALL`.
5. **Negative - Unaligned passage endpoints:** Endpoints do not correspond to wall terminations $\to$ `PASSAGE_ENDPOINTS_UNALIGNED_WITH_WALLS`.
6. **Negative - Zero or degenerate width:** $p_1 == p_2 \to$ `INVALID_PASSAGE_GEOMETRY`.
7. **Negative - Lineage mismatch:** Bad source SHA or missing fields $\to$ `SOURCE_LINEAGE_MISMATCH`.
8. **Metamorphic test:** Invariance under translation and rotation.
9. **No-mutation test:** Verify caller input data structures are not mutated.
10. **Customer retention test:** Verify byte-identical preservation of customer retention rows.
