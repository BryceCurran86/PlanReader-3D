# Architectural Report: Source-Authenticated Structural Wall Thickness Step & Opening Reveal Alignment Authority

**Document ID**: `docs/engineering/antigravity_wall_thickness_step_reveal_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 False Centerline Break at Wall Thickness Steps
- In architectural construction drawings:
  - Walls frequently step in thickness along a continuous facade or structural run:
    1. Exterior cavity masonry ($240$ mm: $110$ mm brick $+ 40$ mm cavity $+ 90$ mm stud) stepping to $90$ mm or $140$ mm framed wall.
    2. Insulated precast panel facade ($200$ mm) stepping to $150$ mm shear wall.
    3. Pilaster projections and structural pier enlargements flanking large window/door apertures.
  - When an opening is positioned at or adjacent to a thickness step:
    - The exterior face of the wall remains continuous and collinear along the building envelope weatherline.
    - The interior face steps transversely by the thickness change $\Delta T = |T_{\text{left}} - T_{\text{right}}| \approx 50$–$150$ mm ($2.8$–$8.5$ pt at 1:100 scale).
    - As a direct geometric consequence, the wall centerline steps transversely by $\Delta y_c = \frac{\Delta T}{2} \approx 1.4$–$4.2$ pt.
- The Failure in Existing Centerline-Based Host Binding:
  - Existing authorities (`OpeningHostBindingProducer`, `OpeningHostFrameProducer`) assume that a continuous wall must have a single collinear centerline across both flanking flanks ($|\Delta y_c| \le 1.0$–$2.0$ pt).
  - When the centerline steps by $2.5$–$5.0$ pt due to an authentic architectural thickness step, the algorithm:
    1. Rejects host binding with `aperture_outside_host_wall_band` or `host_centerline_severed`.
    2. Drops valid window/door candidates before they can reach the opening inventory.
    3. Mistypes the transverse reveal return as an unclosed wall stub.

---

## 2. Inferred Engineering Causes

### 2.1 Exterior Datum Face Alignment vs Centerline Tracking
In architectural drafting standards:
1. Stepped exterior walls are aligned by their **Exterior Weather Face Datum**, not their geometric centerline.
2. The clear opening aperture sits between the terminal jambs referenced to the continuous exterior datum plane.
3. Algorithms that enforce strict centerline collinearity fail on any wall with unequal jamb depths ($T_{\text{left}} \ne T_{\text{right}}$).

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_wall_thickness_step_reveal_authority.py`:
- **Sealed Production & Authority**: `StructuralWallThicknessStepRevealProducer` and `StructuralWallThicknessStepRevealAuthority`.
- **Classification Status**:
  - `STEPPED_WALL_APERTURE_CONFIRMED`: Stepped wall thicknesses reconciled ($T_1, T_2$); exterior datum continuity validated; clear span accurately measured.
  - `ABSTAINED_UNALIGNED_DATUM`: Exterior datum faces diverge by $> 2.0$ pt from collinearity.
  - `ABSTAINED_EXCESSIVE_THICKNESS_DISCREPANCY`: Thickness difference $\Delta T > 15.0$ pt ($> 260$ mm).
  - `ABSTAINED_DEGENERATE_SPAN`: Clear span $< 20.0$ pt or $> 300.0$ pt.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.
