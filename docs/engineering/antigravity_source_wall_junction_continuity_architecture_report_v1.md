# Architecture Report: Source Wall Junction Continuity and Through-Wall Ownership Shadow Authority (Workstream A, Items 2 & 4)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream A, Item 4 ("Recover physical wall junctions and correct continuous wall ownership") and Item 2 ("Fix W2/W3/W4 topology failures affecting wall continuity").

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `docs/engineering/gptmax_w2_source_junction_forensics.md`
  - `pb_wall_room_topology_junction_classifier.py`
  - `tests/test_wall_room_topology_junction_classifier.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
- **Functions Traced:**
  - `pb_wall_room_topology_junction_classifier._group_by_angle`
  - `pb_wall_room_topology_junction_classifier.classify_junctions`
  - `pb_wall_room_topology_junction_classifier.derive_topology_relationships`
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

1. **Junction Graph Splitting & Continuity Loss:**
   - In `pb_wall_room_topology_stage_a.py` and `pb_wall_room_topology_junction_classifier.py`, when a partition wall abuts a major wall at a T-junction, the continuous through-wall is segmented into two separate collinear edges ($E_1, E_2$) meeting at the junction node with the abutting stem ($E_3$).
   - While `pb_wall_room_topology_junction_classifier.py` identifies that $E_1$ and $E_2$ have a `CONTINUES_AS` topology relationship and $E_3$ `BRANCHES_FROM` them, there is no producer-owned authority that unites $E_1$ and $E_2$ into continuous through-wall ownership while ensuring that $E_3$ terminates at the junction without corrupting through-wall continuity.
   - Consequently, downstream consumers either treat $E_1$ and $E_2$ as two separate walls (breaking continuity and distorting wall takeoff calculations) or risk merging $E_3$ into the through-wall (creating false bends or branches).

---

## 2. Inference

- In architectural drawings, at any physical T-junction:
  1. The collinear through-pair ($E_1, E_2$) maintains uninterrupted physical wall ownership straight through the junction node.
  2. The abutting stem ($E_3$) terminates at the junction node (abutting the inner face of the through-wall), without continuing through or splitting through-wall ownership.
- By providing a producer-owned shadow authority `pb_source_wall_junction_continuity_shadow.py` that verifies collinearity, endpoint connectivity within $\le 2.5$ pt snap tolerance, and stroke property consistency, continuous through-wall ownership and terminating stem relationships are definitively resolved without guessing or heuristics.

---

## 3. Proposed Change

Implement `pb_source_wall_junction_continuity_shadow.py`:
- **Selector:** `SourceWallJunctionContinuitySelector` (document_id, revision_id, source_sha256, snapshot_id, page_id, junction_id).
- **Inputs:**
  - `junction_pt`: tuple[float, float]
  - `incident_edges`: sequence of `SourceIncidentWallEdge` (edge_id, start_pt, end_pt, parent_wall_id, stroke_width).
  - `snap_tolerance_pt`: float (default 2.5 pt)
  - `collinear_angle_tolerance_deg`: float (default 3.0 deg)
- **Evaluation Rules (Fail-Closed):**
  1. Validate exact selector lineage (64-hex lowercase SHA-256, non-empty fields).
  2. Validate that each incident edge has one endpoint connecting to `junction_pt` within `snap_tolerance_pt` ($\le 2.5$ pt).
  3. Compute unit departure vectors from `junction_pt` along each edge, and compute angles.
  4. Angle grouping: pair edges whose departure angles are $180^\circ \pm 3.0^\circ$ (collinear through-pair).
  5. Classify junction continuity:
     - **T-Junction (1 pair + 1 single):**
       * Through-pair ($E_1, E_2$) verified continuous (`CONTINUOUS_THROUGH_WALL_RESOLVED`).
       * Single ($E_3$) verified terminating (`ABUTTING_STEM_WALL_TERMINATES`).
     - **L-Corner (2 singles at non-collinear angle):**
       * Verified as a corner bend (`CORNER_WALL_BEND_RESOLVED`).
     - **Collinear Continuation (1 pair, degree 2):**
       * Verified as through-continuation (`COLLINEAR_THROUGH_CONTINUATION_RESOLVED`).
     - **X-Crossing (2 pairs, degree 4):**
       * Verified as 2-way through crossing (`TWO_WAY_THROUGH_CROSSING_RESOLVED`).
     - **Ambiguous:** irregular degree or angle pattern fails closed (`JUNCTION_CONTINUITY_AMBIGUOUS`).
  6. Emit `SourceWallJunctionContinuityRecord` with `status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- References to specific walls, rooms, or benchmark items are illustrative only.
- The algorithm evaluates general geometric node-degree, departure vectors, and collinear angle tolerances deterministically without project-specific hardcoding.

---

## 5. Required Test Matrix (`tests/test_source_wall_junction_continuity_shadow.py`)

1. **Positive - T-Junction Continuity:** Horizontal through-wall + vertical abutting stem verified with through-wall ownership and terminating stem.
2. **Positive - L-Corner:** Two perpendicular edges meeting at 90° verified as a corner wall bend.
3. **Positive - Collinear Continuation:** Two collinear edges meeting at 180° verified as through-continuation.
4. **Positive - X-Crossing:** Four edges forming two orthogonal through-pairs verified as a two-way through-crossing.
5. **Negative - Unaligned endpoints:** Edge endpoint beyond 2.5 pt snap tolerance $\to$ `JUNCTION_ENDPOINT_UNALIGNED`.
6. **Conflict - Irregular 3-way star:** Three edges at 120° (no collinear pair) $\to$ `JUNCTION_CONTINUITY_AMBIGUOUS`.
7. **Negative - Lineage mismatch:** Invalid SHA-256 or empty fields $\to$ `SOURCE_LINEAGE_MISMATCH`.
8. **Metamorphic test:** Invariance under translation and rotation.
9. **No-mutation test:** Verify caller input data structures are not mutated.
10. **Customer retention test:** Verify byte-identical preservation of customer retention rows.
