# Architecture Report: Source-Authenticated Whole-Opening Aperture Structural Authority (v1)

**Date:** 2026-10-27  
**Author:** AntiGravity  
**Lane:** Structural Jamb Detection, Wall Continuity & Whole-Opening Aperture Authority  
**Coordination:** GitHub PR #3462 / Issue #2396  
**Base main SHA:** `449c858db33cf37d7a78ec4fb9a5cf44e2fc11db`  

---

## 1. Executive Summary

In architectural floor plans containing multi-panel glazing assemblies (e.g., ribbon windows, storefronts, and glazed curtain strips), individual glass panes are separated by intermediate vertical mullions and glazing posts. Currently, the source-native physical opening detection stack in `PhysicalOpeningAuthority` suffers from a fundamental structural inversion:
1. **False Positive Sub-element Apertures:** Intermediate glazing post gaps (typically 2.64–2.88 pt / ~1 mm between glass pane end-ticks) form isolated 6-line candidates that satisfy `JAMB_BOUNDED_TWO_FACE_INTERRUPTION`. Because their 0.72 pt capping ticks belong exclusively to that post gap, each post gap achieves unique candidate membership (`len(containing) == 1`) and is mistakenly corroborated as `PHYSICAL_OPENING_EXISTS`.
2. **Missing or Conflicted Whole-Aperture Boundaries:** The true whole physical wall opening (spanning the full window unit across multiple wall layers) fails the rigid coordinate equality test `_same_gap` (`tolerance <= 1e-6 pt`) because real multi-layer walls (brick veneer, cavity air gap, stud/lining, and stepped masonry piers) terminate at stepped or offset returns (e.g., 0.72 pt offset in Maryborough W03). Furthermore, multiple overlapping candidate representations cause candidate ambiguity (`len(containing) > 1` $\to$ `CONFLICT`).

This architecture establishes the **Source-Authenticated Whole-Opening Aperture Structural Authority** (`pb_structural_whole_opening_aperture_authority.py`). It:
- Distinguishes internal glazing subdivisions and post gaps from physical wall openings, classifying them as `INTERNAL_GLAZING_SUBDIVISION_GAP` (negative evidence against physical wall void).
- Establishes source-authenticated terminal jamb roles at the true outer boundaries of the aperture across multi-layer wall faces (heavy structural strokes, pier caps, lining returns).
- Proves host wall continuity beyond terminal jambs.
- Preserves graphic-state and paint uncertainty (unstroked fill boundaries, white masks, clipped strokes fail closed with `status = ABSTAINED`, reason `original_terminal_paint_structural_role_unproven`).
- Emits source-owned `WholeOpeningApertureRecord` and provides candidate filtering that existing authorities (`PhysicalOpeningAuthority`, `OpeningHostBindingAuthority`) can validate in shadow mode.

---

## 2. Observed Repository Behavior

### 2.1. `PhysicalOpeningAuthority` (`pb_physical_opening_authority.py`)
- **`_visible_structural_candidates(seed, records)` (lines 2650–2959):** Discovers exact structural openings using collinear record pairs and `_face_break`.
  - Wall face breaks are paired via `_same_gap(first_break, second_break)` requiring `abs(first.gap_start - second.gap_start) <= 1e-6` and `abs(first.gap_end - second.gap_end) <= 1e-6`.
  - Jamb segments are located via `indexed_segment_matches(first_break.start_point, second_break.start_point)` which searches for a *single* segment whose endpoints match within `1e-6`.
  - On Maryborough page 7, the inner glass pane lines of multi-panel windows (e.g. W01, W02, W03, W05) have thickness $0.72\text{ pt}$ and post gaps $2.64\text{--}2.88\text{ pt}$. At each post gap, perpendicular ticks of length $0.72\text{ pt}$ cap the glass panes. These 6 segments form a perfect `JAMB_BOUNDED_TWO_FACE_INTERRUPTION` candidate.
- **`prove_existence(selector)` (lines 4161–4400):**
  - Evaluates candidates containing the queried observation.
  - If `len(containing) == 1`: checks dimension cap opposition and unstroked fill opposition. If neither opposes, returns `status = CORROBORATED` with `proposition = PHYSICAL_OPENING_EXISTS` and `STRUCTURAL_OPENING_EXISTENCE_RESOLVED`.
  - For internal glazing posts, no dimension annotation or unstroked fill opposes the tick, so every internal post gap is corroborated as `PHYSICAL_OPENING_EXISTS`!
  - For the true whole opening (e.g., W03 spanning $1343.12\text{ to }1550.00\text{ pt}$), the lining return at $y=1550.00$ and core pier cap at $y=1550.72$ create rival candidates with $0.72\text{ pt}$ span differences. Querying member lines yields `len(containing) > 1` $\to$ `AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES` (`status = CONFLICT`).

### 2.2. Sibling Read-Only Shadows (Merged #3912, #3955, #3956, #3957)
- **`pb_strip_structural_assessment_shadow.py` (#3912):** Re-derives physical opening status for a nominated glazing strip, observing that existing authority only yields fragmented post gaps (`FRAGMENTS_ONLY`) or rival conflicts.
- **`pb_strip_face_family_shadow.py` (#3955):** Inventories parallel strokes across strip extents, identifying continuous through lines vs broken lines.
- **`pb_glazing_anatomy_inventory_shadow.py` (#3957):** Evaluates glazing cells gate-by-gate (g1..g8) for glazing subassembly anatomy.
- **`pb_subfloor_ink_census_shadow.py` (#3956):** Documents that sub-0.5 pt strokes dropped by extraction can complete tick anatomy, but notes that graphic-state paint (white fill masks, clipping) can obscure terminal roles.

### 2.3. Downstream Receiving Path
- **`OpeningHostBindingProducer.publish` (`pb_opening_host_binding_authority.py`, lines 495–520):**
  - Re-proves left and right opening selectors using `physical_opening_authority.prove_existence`.
  - Requires both selectors to be `CORROBORATED` and `PHYSICAL_OPENING_EXISTS`.
  - When fed false post gaps, it attempts to bind $1\text{ mm}$ gaps to the wall. When fed true whole openings, it fails because `PhysicalOpeningAuthority` is in `CONFLICT` or `ABSTAINED`.
- **`pb_live_opening_area_quantity_publication.py` & `pb_live_opening_count_quantity_publication.py`:**
  - Consume verified `OpeningHostBindingRecord` and `PhysicalOpeningExistenceRecord` to publish customer quantities.

---

## 3. Inferred Caller Wiring

- `PhysicalOpeningAuthority` requires an authoritative discrimination gate to filter out internal glazing sub-elements before candidate promotion.
- Downstream authorities require whole-aperture evidence where the terminal jambs and aperture extent are reconciled across multi-layer wall faces.
- Any new authority must follow the sealed producer / frozen authority contract, remain in shadow mode (`status = EvidenceResolutionStatus.CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`), and avoid isolated inventory dead-ends by providing concrete integration hooks for `PhysicalOpeningAuthority` and `OpeningHostBindingAuthority`.

---

## 4. Proposed Changes

### 4.1. New Authority: `pb_structural_whole_opening_aperture_authority.py`
1. **Sealed Producer / Frozen Authority Contract:**
   - `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, `_RECORD_SEAL` singletons prevent bypass.
   - `StructuralWholeOpeningApertureProducer` constructs and proves whole-aperture structural records.
   - `StructuralWholeOpeningApertureAuthority` provides immutable query resolution.
2. **Glazing Subdivision Discrimination:**
   - Detects intermediate glazing post gaps ($span \le 5.0\text{ pt}$, $depth \le 2.0\text{ pt}$, bounded by glass pane ticks, situated strictly between outer terminal boundaries of a multi-panel glazing assembly, with host wall faces continuing unbroken outside the strip).
   - Issues `GlazingSubdivisionDiscriminationRecord` with `is_internal_subdivision = True` and reason code `INTERNAL_GLAZING_SUBDIVISION_GAP`.
   - Provides `filter_opening_candidates` to purge these false voids from physical opening candidate pools.
3. **Whole-Aperture Terminal Jamb Detection:**
   - Identifies the outer boundaries of the window aperture (`frame_along = [a_lo, a_hi]`).
   - Evaluates perpendicular strokes across the wall band at each terminal:
     * Heavy structural jamb strokes (`stroke_width >= 0.8 pt`).
     * Masonry pier caps and returns.
     * Stud/lining returns.
     * Composite jamb chains spanning across multi-layer wall bands (outer masonry, cavity, inner lining).
4. **Host Wall Continuity Verification:**
   - Verifies that beyond the terminal jambs ($along < a_{lo}$ and $along > a_{hi}$), physical wall faces continue uninterrupted.
5. **Graphic-State & Paint Uncertainty Preservation:**
   - Segments formed solely by unstroked fill boundaries, white masks, or clipped strokes fail closed with `status = EvidenceResolutionStatus.ABSTAINED` and reason `original_terminal_paint_structural_role_unproven`.
   - Stepped pier offsets within tolerance ($0.72\text{ pt}$ lining offset in W03) are recognized as composite interfaces with reason code `AMBIGUOUS_MULTI_LAYER_OFFSET` while bounding the aperture.
   - Unclosed or ambiguous returns issue `AMBIGUOUS_STRUCTURAL_BOUNDARY`.
6. **Consumer Validation Hook:**
   - Emits `WholeOpeningApertureRecord` containing exact aperture spans, wall band extents, terminal jamb observation IDs, host face IDs, and demoted subdivision IDs.

### 4.2. Comprehensive Test Suite: `tests/test_structural_whole_opening_aperture_authority.py`
- Synthetic multi-panel ribbon window with internal glazing posts (positive whole aperture, positive post discrimination).
- Adversarial single-pane window without internal posts (preserves standard single aperture).
- Look-alike non-opening interior post gap (correctly rejected as wall opening).
- Multi-layer wall with stepped pier returns (W03-style 0.72 pt lining offset).
- Unstroked fill / white mask boundary (abstains on graphic-state uncertainty).
- Invariance tests: 90/180/270-degree rotation, translation, stroke ordering, and segment splitting.
- Deterministic replay, stable ID hashing, and immutability checks.
- Original-source regression tests against Maryborough page 7 (W01, W02, W03, W05).

---

## 5. Benchmark Observations (Firewall Protected)

The following benchmark facts are observed for verification only and must **never** drive algorithms, tolerances, or search parameters:
- Reference takeoff for Maryborough service station (`reference_takeoff.json`):
  * `maryborough-window-tagged-count`: expected 6 (`W01`..`W06`).
  * Nominal gross framed opening areas: W01 = 6.84 m², W02 = 7.79 m², W05 = 14.4115 m², W06 = 1.47 m².
  * W03 and W04 window areas remain `UNRESOLVED` in `unresolved_items.json`.
- Extractor/evaluator firewall: Algorithms must be derived strictly from source vector geometry, physical wall continuity, and graphic-state properties. Global 2.5 pt snap and 20,000 primitive cap remain inviolate.
