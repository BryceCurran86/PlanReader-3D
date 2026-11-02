# Architectural Report: Source-Authenticated Structural Door Threshold vs Wall Continuity Discrimination Authority

**Document ID**: `docs/engineering/antigravity_door_threshold_wall_continuity_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Door Aperture Obliteration by Spurious Wall Continuity
- In architectural drawings, door openings through walls are accompanied by thin auxiliary linework:
  1. Door threshold bridge lines indicating floor level or material changes.
  2. Door leaf representations (e.g. 45° or 90° swing arcs, sliding leaves, pocket door tracks).
  3. Refrigerator/freezer thermal breaks and door stop profiles.
- In naive vector linking and wall tracing routines, any continuous line connecting the two sides of a wall void is classified as wall continuity. As a direct consequence:
  - The clear structural aperture is sealed shut.
  - The door opening candidate is destroyed before reaching the opening inventory.
  - Downstream room area, floor finish boundary, and door schedule correspondence authorities fail because the aperture does not exist in the spatial graph.
- Concrete examples across benchmark plans:
  - **Maryborough Service Station (Page 7 vs Page 11 Detail)**: The cold-storage FREEZER room door `D17` sits in an insulated sandwich panel wall with structural stroke width $0.96$ pt. Left and right structural jambs terminate at $x \approx 476.16$ and $x \approx 521.52$ pt (a clear opening of $45.36$ pt $\approx 800$ mm). Spanning the threshold is a thin $0.48$ pt line representing the sliding door leaf / thermal seal. Unauthenticated line tracing treats this thin line as a continuation of the insulated wall panel, falsely creating an unbroken wall from $x = 440.0$ to $x = 560.0$ and obliterating `D17`.
  - **Lot 16 (Page 3)**: Internal timber-stud passage doors have $0.24$–$0.48$ pt threshold transition lines spanning between $0.72$ pt plasterboard/stud jamb returns. Treating threshold lines as structural wall faces closes the door aperture.

### 1.2 Stepped Recess & Lintel Look-Alike Misclassifications
- Conversely, an unconstrained opening detector that ignores stroke weight hierarchy and terminal return topology will falsely classify:
  - Wall thickness steps (pilasters, recesses, pier projections).
  - Overhead ceiling bulkheads or dropped lintels.
  - Unclosed partition runs.
- Structural discrimination must demand authentic structural jamb termination and hierarchical stroke classification before declaring an aperture.

---

## 2. Inferred Engineering Causes

### 2.1 The Stroke Weight Hierarchy Rule (AS 1100 / ISO 128)
In architectural and structural CAD drafting:
1. **Primary Structural Cut Lines** ($\ge 0.70$ pt, typically $0.72$–$1.20$ pt, e.g. $0.96$ pt on Maryborough): Represent the physical, loadbearing, or insulated building envelope cut by the horizontal plan projection plane.
2. **Secondary Non-Structural Linework** ($\le 0.50$ pt, typically $0.18$–$0.48$ pt, e.g. $0.48$ pt on Maryborough): Represent sills, thresholds, floor transitions, door swings, and sliding leaves.
3. When evaluating a line spanning an aperture void:
   - If $W_{\text{span}} \le 0.50$ pt, it is non-structural threshold or door leaf ink; it MUST be vetoed as wall continuity.
   - If $W_{\text{span}} \ge 0.70$ pt, it constitutes a solid continuous wall run; no physical opening exists.
   - If $0.50 < W_{\text{span}} < 0.70$ pt, stroke weight is ambiguous; the authority must fail closed (`ABSTAINED`).

### 2.2 Terminal Jamb Return Geometry
A genuine door opening requires:
1. Opposed terminal jamb endpoints where the structural wall outlines terminate.
2. A clear aperture width $W_{\text{clear}} = \|\mathbf{p}_{\text{right}} - \mathbf{p}_{\text{left}}\|$ conforming to architectural door clearance ranges ($400$ mm to $2500$ mm, or $20.0$ pt to $150.0$ pt at standard scales).
3. Collinear or parallel alignment with the parent wall axis.

### 2.3 Multiview Translation Verification (Plan-to-Detail)
In plans with matching detail views:
- An authentic opening must translate across corresponding views by an authenticated rigid translation vector (e.g. Maryborough Page 7 to Page 11 detail: $dx = +77.76 \pm 0.5$ pt).
- Spurious candidates or mismatched drawing features (e.g. rival offset $+43.92$ pt) fail the multi-view gate and must be rejected.

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_door_threshold_wall_continuity_authority.py`:
- **Sealed Production & Authority**: `StructuralDoorThresholdWallContinuityProducer` and `StructuralDoorThresholdWallContinuityAuthority`.
- **Classification Status**:
  - `DOOR_APERTURE_CONFIRMED`: Structural jambs confirmed, threshold bridge vetoed as wall continuity, clear opening validated.
  - `SOLID_WALL_CONTINUITY`: Spanning ink is structural; wall is continuous without aperture.
  - `ABSTAINED_AMBIGUOUS_STROKE`: Stroke weight falls between thresholds ($0.50 < W < 0.70$ pt).
  - `ABSTAINED_MULTIVIEW_MISMATCH`: Multi-view candidate does not match authenticated translation ($dx = +77.76$ pt).
  - `ABSTAINED_OUT_OF_BOUNDS_SPAN`: Clear span is degenerate ($< 20.0$ pt or $> 150.0$ pt).
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.

---

## 4. Acceptance Criteria & Verification Plan

1. **Synthetic Positives**: Standard door opening with $0.96$ pt wall jambs and $0.48$ pt threshold bridge correctly vetoes wall continuity and confirms door aperture.
2. **Synthetic Solid Wall Negatives**: Unbroken wall with $0.96$ pt spanning line correctly rejects aperture and confirms solid wall continuity.
3. **Ambiguous Stroke Negative**: Ambiguous $0.62$ pt spanning stroke fails closed with `ABSTAINED`.
4. **Multiview Verification**: Multi-view candidate with $dx = +77.76$ pt succeeds; rival candidate with $dx = +43.92$ pt fails closed.
5. **Maryborough D17 Freezer Regression**: Exact source geometry from Maryborough p7 and p11 ($x \in [476.16, 521.52]$, $span = 45.36$ pt) resolves cleanly.
6. **Invariance Tests**: Reversal of jamb ordering (right-to-left vs left-to-right) and translation invariance preserve stable contract IDs.
