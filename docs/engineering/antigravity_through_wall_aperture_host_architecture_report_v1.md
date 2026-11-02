# Architectural Report: Source-Authenticated Structural Through-Wall Aperture Hosting & Continuous Host Frame Shadow Authority

**Document ID**: `docs/engineering/antigravity_through_wall_aperture_host_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Structural Host Wall Fragmentation & Opening Rejection
- In `OpeningHostBindingProducer.publish` (`pb_opening_host_binding_authority.py`) and `OpeningHostFrameProducer._shared_host_frame` (`pb_opening_host_frame_authority.py`):
  - Physical openings require binding to an authenticated structural host wall (`OpeningHostBindingRecord`) and whole-wall frame (`OpeningHostFrameRecord`).
  - In existing host binding logic, candidate host walls are required to have continuous centerline coverage that strictly overlaps or envelopes the opening void.
  - When an opening is detected, the wall is frequently fragmented into isolated sub-segments, or adjacent openings separated by narrow structural piers fail single-owner assumptions.
  - Across benchmark projects:
    - In **Lot 16 Power (Page 3)**: 6 of 13 unsigned openings fail with `structural_host_unavailable` due to `raster_source_band_left_source_primitive_unmapped` or `raster_source_band_right_source_primitive_unmapped`. Openings `81a45c3a33c2a4c0bfdf243aa45a780d` and `f819752382d44a00d9f28feca4b00787` share a $4.8$ pt stud pier; opening `33d277d4c6b6ce758b0594f9d47ce4d8` has a $3.84$ pt solid flank that falls below the $4.0$ pt center tolerance.
    - In **Maryborough Service Station (Page 7)**: The eastern exterior masonry wall extends continuously from $y = 558.08$ to $y = 1959.92$ (span $1401.84$ pt $\approx 24.7$ m), with thickness $\approx 16.32$ pt ($x \in [1110.72, 1127.04]$). Along this single structural through-wall, three multi-bay window assemblies sit:
      - `W05`: span $y \in [646.40, 1076.48]$ ($430.08$ pt)
      - `W03`/`W01`: span $y \in [1343.12, 1550.00]$ ($206.88$ pt)
      - `W02`: span $y \in [1557.44, 1789.76]$ ($232.32$ pt)
    - Between `W03` ($y = 1550.00$) and `W02` ($y = 1557.44$), there is an authentic **$7.44$ pt masonry dividing pier** ($262$ mm at 1:100 scale).
    - In legacy authorities, this narrow $7.44$ pt pier does not form an independent long wall candidate; as a consequence, `W03` and `W02` cannot authenticate their host wall, resulting in `opening_host_frame_host_unavailable` and `whole_wall_frame_unavailable`.

---

## 2. Inferred Engineering Causes

### 2.1 The Through-Wall Architectural Continuity Rule
In structural and architectural engineering:
1. An exterior loadbearing wall or internal shear wall containing windows and doors is a **continuous structural through-wall**, not a collection of disconnected independent wall islands.
2. The wall is structurally continuous:
   - Below the opening sill: supported by continuous footings and sill masonry.
   - Above the opening head: spanned by continuous bond beams, lintel plates, or timber headers.
   - At the jambs: tied into structural piers that resist shear and lateral loads.
3. Carving out openings from the wall centerline without maintaining the parent through-wall identity destroys through-wall continuity and causes downstream host authorities to drop valid openings.

### 2.2 Narrow Inter-Aperture Pier Misclassification
In multi-window facades and dense corridor door layouts:
1. Structural piers between adjacent openings often have widths between $5$ pt and $30$ pt ($175$ mm to $1050$ mm).
2. Existing algorithms treat sub-threshold flanks ($< 4.0$ pt) or short pier segments as segmentation noise or unmapped primitives.
3. Rather than discarding these solid flanks, the authority must recognize them as **Inter-Aperture Structural Piers** that connect the adjacent terminal jambs of consecutive openings.

### 2.3 Whole-Wall Frame Mathematical Consistency
A whole-wall opening frame requires:
- $\text{axis\_unit}$: normalized tangent along the through-wall centerline.
- $\text{normal\_unit}$: normalized normal perpendicular to the wall.
- $\text{origin\_pt}$: datum point at the wall start.
- $u_0, u_1$: projection of the opening's terminal jamb stations along the host wall axis ($0 \le u_0 < u_1 \le L_{wall}$).
- $\text{whole\_wall\_length\_pt}$: total length $L_{wall}$ of the continuous structural wall.
- $\text{wall\_thickness\_pt}$: outer-face to inner-lining transverse depth.

---

## 3. Proposed Repair & Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_through_wall_aperture_host_authority.py`:
- **Sealed Production & Authority**: `StructuralThroughWallApertureHostProducer` and `StructuralThroughWallApertureHostAuthority`.
- **Data Structures**:
  - `ContinuousThroughWallCandidate`: Represents the master loadbearing wall run.
  - `InterAperturePierRecord`: Represents the solid wall pier bridging adjacent openings ($W_{pier} \in [4.0, 50.0]$ pt).
  - `ThroughWallHostedOpeningRecord`: Reconciles the whole opening aperture (`WholeOpeningApertureRecord`) with the continuous host wall, providing exact frame parameters ($u_0, u_1, L_{wall}, T_{wall}$).
- **Fail-Closed Structural Gates**:
  - Transverse wall obstruction: If an unrelated transverse wall crosses the opening void, fails closed with `EvidenceResolutionStatus.ABSTAINED` and `first_remaining_gate = "host_through_wall_obstructed"`.
  - Angular misalignment: If the opening span angle deviates from the through-wall axis by $> 0.5^\circ$, fails closed with `first_remaining_gate = "aperture_wall_axis_misaligned"`.
  - Transverse displacement: If the opening center offset exceeds the wall half-thickness, fails closed with `first_remaining_gate = "aperture_outside_host_wall_band"`.
  - Missing jambs: Openings lacking authenticated terminal jambs cannot form a through-wall host frame.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero mutation of baseline customer outputs or frozen benchmarks.

### 3.2 Verification Strategy
- Synthetic positive: Multi-opening facade (3 windows) hosted along a continuous 25 m through-wall with two intermediate masonry piers.
- Synthetic negative: Misaligned opening angle ($> 1^\circ$).
- Synthetic negative: Transverse wall crossing opening void.
- Synthetic negative: Opening displaced outside wall band.
- Metamorphic invariance: Rotation, translation, and scale transformations.
- Input ordering invariance: Reordering openings along the wall.
- Deterministic regression: Maryborough Page 7 East Wall (`W05`, `W03`/`W01`, `W02`, and the $7.44$ pt dividing pier).

---

## 4. Benchmark Observations That Must Not Influence Implementation

- Frozen benchmark truth across Maryborough and Lot 16 is completely untouched.
- The 20,000 primitive cap and 2.5 pt snap rules remain invariant.
- No expected quantities, opening dimensions, or customer rows are hardcoded.
