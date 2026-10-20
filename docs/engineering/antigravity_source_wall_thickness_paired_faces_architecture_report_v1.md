# Architecture Report: Producer-Owned Source Wall Thickness and Paired Wall Faces Shadow Authority (Item 6)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Source Wall Thickness and Paired Wall Faces Shadow Authority** (`pb_source_wall_thickness_paired_faces_shadow.py`), resolving Workstream A, Item 6 of the Autonomous Core Accuracy Engineering Mission.

The primary blockers addressed are:
1. **Unproved Wall Thickness in Wall Candidates:** Wall candidates in `assemble_wall_candidates` start with `thickness_authority = MeasurementAuthorityType.PROVISIONAL` and `thickness_m = None`. Top-level `CORROBORATED` status is deliberately capped by `WallCandidate.__post_init__` because physical thickness requires independent source corroboration.
2. **Ambiguous Paired Face Ownership:** Line pairing without canonical medial orientation, overlap validation, drafting motif negative filtering, and scale cross-checks risked assigning arbitrary gaps or mistaking non-wall linework (e.g., parallel hatch lines, dimension ticks) for structural wall faces.
3. **Producer-Owned Authority Gap:** `pb_wall_thickness_face_authority.py` correctly locked out caller-constructed `WallThicknessEvidence` with a `TypeError` until a true source-derived producer existed.

This module provides a strictly sealed, source-grounded authority that authenticates paired wall faces, computes the exact medial centerline, evaluates physical thickness with scale or documented dimensions, verifies left/right face stability, and serializes genuine OGC Well-Known Binary (WKB) geometry.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Implements standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons to prevent external instantiation or tampering.
- Factory method `SourceWallThicknessPairedFacesProducer.create()` produces the mutable producer.
- Once populated, calling `.authority()` returns a frozen, immutable `SourceWallThicknessPairedFacesAuthority` mapping selectors to results.

### 2. Physical Face Pairing & Geometric Gates
- **Lineage Verification:** Primitives must belong to the exact `(document_id, revision_id, source_sha256, snapshot_id, page_id)`.
- **Negative Drafting Motif Guard:** Primitives classified as negative drafting motifs (dimension ticks, grid lines, hatching strokes, furniture contours) are rejected with `NEGATIVE_DRAFTING_MOTIF_REJECTED`.
- **Parallelism Gate:** Face strokes $A$ and $B$ must have angle alignment within $\le 2.0^\circ$ ($|t_a \times t_b| \le 0.035$). Non-parallel strokes fail with `PAIRED_FACES_NON_PARALLEL`.
- **Projection Overlap Gate:** The orthogonal projection of $B$ onto $A$ must overlap by $\ge 45\%$ of $\min(L_a, L_b)$ and $\ge 12.0$ pt. Fails with `PAIRED_FACES_OVERLAP_INSUFFICIENT`.
- **Gap Bounds Gate:** Physical perpendicular distance must be in plausible structural range ($0.8 \le \text{gap\_pt} \le 18.0$ pt if uncalibrated; $0.04 \le \text{gap\_m} \le 0.45$ m if calibrated). Fails with `PAIRED_FACES_GAP_OUT_OF_RANGE`.
- **Thickness Calculation & Cross-Check:**
  - If scale is authenticated ($\text{px\_per\_m} > 0$), $\text{thickness\_m} = \text{gap\_pt} / \text{px\_per\_m}$.
  - If documented/figured thickness is available, cross-check against calibrated gap ($\le 15\%$ deviation). Disagreement yields `WALL_THICKNESS_CONFLICT`.
  - Zero or negative thickness strictly rejected (`WALL_THICKNESS_ZERO_REJECTED`, `WALL_THICKNESS_NEGATIVE_REJECTED`).
- **Canonical Orientation & Stable Face Identity:**
  - Points along the medial axis are sorted in canonical physical forward order (lexicographically).
  - Normal $N = (-u_y, u_x)$ points unambiguously to the Left Face at $+ \text{gap}/2$ and Right Face at $- \text{gap}/2$.
  - Reversing input stroke direction never swaps Left and Right face identities.
- **Genuine OGC WKB Serialization:**
  - Little-endian binary byte format for LineString (centerline, face_left, face_right) and Polygon (bounding wall polygon).

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
