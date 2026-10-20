# Architecture Report: Producer-Owned Source Structural Identity and Fragment Provenance Shadow Authority (Items 9 & 25)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Source Structural Identity and Fragment Provenance Shadow Authority** (`pb_source_structural_identity_fragment_provenance_shadow.py`), resolving:
- **Workstream A, Item 9:** "Implement deterministic structural identity across fragmented linework."
- **Workstream C, Item 25:** "Preserve primitive provenance through splitting, clipping and snapping."

The primary blockers addressed are:
1. **Structural Fragmentation Across Topology Phases:** In Stages W2 and W3, continuous architectural wall runs are split at geometric intersections into disjoint edge fragments. Downstream phases frequently treat these fragments as isolated wall candidates, leading to duplicate candidate-ID collisions (Item 3), broken wall continuity, and loss of original primitive extent.
2. **Loss of Primitive Provenance:** As linework undergoes clipping to viewport boundaries and snapping to graph nodes, child fragments can lose their connection to the parent PDF path item. Without a canonical structural run authority, it is impossible to reconstruct whether a wall was originally a continuous 10-meter structural run broken only by a door opening, or two unrelated collinear stubs.
3. **Deterministic Structural Run Identity:** This module aggregates all child edge fragments sharing a parent primitive, verifies their collinear parameterization along the parent vector, computes exact covered intervals and void gaps, and mints an immutable `structural_identity_id` that downstream agents can consume to track physical continuous wall ownership.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Employs standard internal seals (`_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL`) ensuring all objects are minted only through trusted internal writer boundaries.
- Factory method `SourceStructuralIdentityProducer.create()` produces the mutable producer.
- Once evaluated, calling `.authority()` yields an immutable `SourceStructuralIdentityAuthority` providing frozen O(1) resolution via `SourceStructuralIdentitySelector`.

### 2. Geometric Collinear Parameterization & Interval Analysis
- **Parent Primitive Vector Parameterization:**
  - Given parent endpoints $P_1 = (x_1, y_1), P_2 = (x_2, y_2)$, length $L = |P_2 - P_1|$ and unit tangent $U = (P_2 - P_1) / L$.
  - Each child fragment $E_k = (Q_{k,1}, Q_{k,2})$ is tested for collinearity:
    - Normal distance $|(Q_{k,i} - P_1) \cdot N| \le 0.5$ pt (with $N = (-U_y, U_x)$).
    - Child orientation dot product $|U_k \cdot U| \ge 0.999$.
    - Non-collinear fragments fail closed with `FRAGMENT_NON_COLLINEAR`.
  - Child projection parameters $t_{k,1} = (Q_{k,1} - P_1) \cdot U$, $t_{k,2} = (Q_{k,2} - P_1) \cdot U$.
  - Fragment interval is $[t_{k,\min}, t_{k,\max}] \subseteq [0, L]$.
- **Interval Merging and Gap Reconstruction:**
  - Overlapping or touching intervals are merged using `merge_intervals`.
  - Uncovered intervals along $[0, L]$ represent void gaps (e.g. wall openings, intersecting beams, or clipped regions).
  - Total coverage ratio is $\sum \text{len}(\text{interval}_i) / L$.
  - If coverage $\ge 0.99$, record is marked `FRAGMENT_RUN_COMPLETE`; if partial, marked `FRAGMENT_RUN_PARTIAL`.

### 3. Stable Contract & WKB Geometry
- Minted `structural_identity_id`:
  - Deterministically hashed from `(document_id, revision_id, source_sha256, page_id, parent_primitive_id)`.
  - Provides downstream consumers with a unified identity across all sibling fragments.
- Serialized OGC Well-Known Binary (WKB):
  - Encodes the complete reconstructed structural run as an OGC LineString (if unbroken) or MultiLineString (if partitioned by openings).

### 4. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
