# Architecture Report: Producer-Owned Source Drafting Motif Negative Evidence Shadow Authority (Items 5 & 28)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream A, Item 5 ("Prevent hatching, grid lines, furniture and dimension marks being mistaken for walls") and Workstream C, Item 28 ("Eliminate structural false positives using typed negative evidence without deleting legitimate candidates prematurely").

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `docs/engineering/gptmax_aligned_fragment_motif_distinct_20261016.md`
  - `pb_structural_wall_ink_shadow.py`
  - `pb_physical_wall_candidate_authority.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
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

1. **The Motif Contamination Problem:**
   - Architectural CAD drawings contain thousands of non-wall linework primitives:
     * **Dimension Ticks & Witness Lines:** e.g. primitive `:713` in Lot16, a 4.5 pt line at 45 degrees, which failed DISTINCT in opening host frames (#2396).
     * **Grid Lines:** Long, thin single-stroke lines (stroke width $< 0.6$ pt) spanning across the sheet or building with no paired face partner.
     * **Hatch Strokes:** Dense, repeated arrays of parallel single-segment strokes (e.g. insulation or wet area hatching) at pitch $< 15$ pt.
     * **Furniture & Fixtures:** Small closed loops or compact multi-segment paths (e.g. gas cylinder symbols in 3Laurel §9.4 that falsely created a sliding door host!).
2. **Current Gate Behavior:**
   - When these drafting primitives enter `pb_physical_wall_candidate_authority`, they inflate segment counts, trip safety caps, and generate false wall candidates and false opening hosts.
   - However, naive filtering risks prematurely deleting legitimate wall candidates (e.g. short wall returns, jamb piers, or thin partition walls).

---

## 2. Inference

- Non-wall drafting motifs possess distinct geometric and relational properties:
  1. *Dimension Ticks:* Short length ($\le 12$ pt), angled at 45° or perpendicular to dimension lines, lacking parallel wall face partners.
  2. *Grid Lines:* Very long single strokes without a parallel face partner at structural wall thickness ($t \in [3.0, 30.0]$ pt).
  3. *Hatch Strokes:* Repeated parallel lines with narrow pitch ($< 15$ pt) and high repetition count ($\ge 4$).
  4. *Furniture/Fixtures:* Compact closed loops (area $< 4000$ sq pt, perimeter $< 250$ pt) situated inside room envelopes without connection to structural perimeter walls.
- A producer-owned shadow classifier that computes typed negative evidence (`DRAFTING_MOTIF_DIMENSION_TICK`, `DRAFTING_MOTIF_GRID_LINE`, `DRAFTING_MOTIF_HATCH_STROKE`, `DRAFTING_MOTIF_FURNITURE_FIXTURE`) while strictly protecting verified paired wall faces and room boundary edges enables safe downstream disambiguation without deleting legitimate candidates prematurely.

---

## 3. Proposed Change

Implement `pb_source_drafting_motif_negative_evidence_shadow.py`:
- **Selector:** `SourceDraftingMotifSelector` (document_id, revision_id, source_sha256, snapshot_id, page_id).
- **Inputs:**
  - `candidate_segments`: sequence of candidate linework segments with id, coordinates `(x1, y1, x2, y2)`, stroke width, and optional path index.
  - `known_wall_paired_face_ids`: set of primitive IDs already proven to form paired wall faces (strictly protected from negative classification).
- **Classification Rules:**
  1. If primitive is in `known_wall_paired_face_ids` $\to$ `SUBTYPE_STRUCTURAL_WALL_RUN`.
  2. If primitive is a short stroke ($\le 12$ pt) at 45° or forming part of a dimension chain $\to$ `SUBTYPE_DIMENSION_TICK`.
  3. If primitive belongs to a dense parallel cluster ($\ge 4$ strokes, pitch $\le 15$ pt, aspect $\ge 4$) $\to$ `SUBTYPE_HATCH_STROKE`.
  4. If primitive is an isolated long thin line ($L \ge 200$ pt, width $< 0.6$ pt) spanning without a parallel partner within 30 pt $\to$ `SUBTYPE_GRID_LINE`.
  5. If primitive belongs to a small closed loop (perimeter $< 250$ pt, bbox area $< 4000$ sq pt) $\to$ `SUBTYPE_FURNITURE_FIXTURE`.
  6. Otherwise $\to$ `SUBTYPE_UNPROVEN_DRAFTING_INK` (retained, fail-closed).
- **Outputs:**
  - `SourceDraftingMotifRecord` with primitive-by-primitive typed verdicts, summary counts, and safe retention guarantees.
  - Status `EvidenceResolutionStatus.CANDIDATE`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- References to Lot16, 3Laurel, Maryborough, or specific primitive IDs (`:713`, etc.) are illustrative only.
- The algorithm evaluates general geometric relationships (length, width, orientation, repetition, spacing, loop closure) deterministically without project-specific hardcoding.

---

## 5. Required Test Matrix (`tests/test_source_drafting_motif_negative_evidence_shadow.py`)

1. **Positive - Dimension ticks:** 45-degree short ticks identified as `SUBTYPE_DIMENSION_TICK`.
2. **Positive - Grid lines:** Long thin line without partner identified as `SUBTYPE_GRID_LINE`.
3. **Positive - Hatching:** Array of parallel strokes at consistent pitch identified as `SUBTYPE_HATCH_STROKE`.
4. **Positive - Furniture/fixture:** Small closed loop (e.g. toilet/gas cylinder symbol) identified as `SUBTYPE_FURNITURE_FIXTURE`.
5. **Protection - Genuine paired wall faces:** Parallel wall faces are strictly protected as `SUBTYPE_STRUCTURAL_WALL_RUN`.
6. **Negative - Lineage mismatch:** Bad SHA-256 or empty fields $\to$ `SOURCE_LINEAGE_MISMATCH`.
7. **Metamorphic test:** Invariance under translation.
8. **No-mutation test:** Verify caller input data structures are not mutated.
9. **Customer retention test:** Verify byte-identical preservation of customer retention rows.
