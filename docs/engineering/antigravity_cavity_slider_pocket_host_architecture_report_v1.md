# Architectural Report: Source-Authenticated Structural Cavity Slider Lead Jamb & Split-Stud Pocket Host Authority

**Document ID**: `docs/engineering/antigravity_cavity_slider_pocket_host_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Aperture Over-Measurement and Pocket Wall Severance
- In architectural floor plans:
  - Cavity sliding pocket doors retract into the hollow interior of an adjacent partition wall.
  - The architectural assembly consists of:
    1. **Strike Jamb (Lead Jamb)**: Solid timber/steel closing stud where the door leaf latches.
    2. **Clear Opening Aperture**: Clear passage width between the strike jamb and pocket mouth (receiver jamb) ($W_{\text{clear}} \approx 720$–$920$ mm / $40.8$–$52.1$ pt at 1:100 scale).
    3. **Pocket Split-Stud Envelope**: Hollow wall section framed with split timber/steel studs ($19$ mm) flanking the internal pocket cavity ($40$ mm cavity in a $90$ mm wall).
    4. **Back Stud**: Solid framing stud at the rear of the pocket cavity.
- Failure Modes in Unauthenticated Vector Tracing:
  - Naive wall linkers encounter the pocket cavity and mistake the two thin split-stud walls for two independent thin partitions, or they truncate the continuous host wall at the lead jamb and treat the pocket frame as a severed dead wall stub.
  - Consequently, downstream host binding fails with `no_authenticated_host_wall_band` or `aperture_outside_host_wall_band`.
  - In reverse errors, the entire assembly length from the strike jamb to the back stud ($W_{\text{clear}} + D_{\text{pocket}} \approx 2 \times W_{\text{clear}}$) is measured as the door opening width, falsely doubling the door schedule takeoff!

---

## 2. Inferred Engineering Causes

### 2.1 Clear Aperture vs Pocket Depth Separation
In architectural CAD standards:
1. **Clear Passage Aperture**:
   $$W_{\text{clear}} = \|\mathbf{p}_{\text{pocket\_mouth}} - \mathbf{p}_{\text{strike\_jamb}}\|$$
2. **Pocket Retraction Depth**:
   $$D_{\text{pocket}} = \|\mathbf{p}_{\text{back\_stud}} - \mathbf{p}_{\text{pocket\_mouth}}\|$$
3. Total pocket door unit length is:
   $$L_{\text{total}} = W_{\text{clear}} + D_{\text{pocket}} \approx 2 \times W_{\text{clear}}$$
4. Physical Retraction Feasibility: For the door leaf to retract fully, $D_{\text{pocket}} \ge W_{\text{clear}} - 50$ mm ($2.8$ pt at 1:100).
5. The authority must strictly distinguish the clear passage width from the pocket retraction depth while binding the full unit to the continuous host through-wall frame.

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_cavity_slider_pocket_host_authority.py`:
- **Sealed Production & Authority**: `StructuralCavitySliderPocketHostProducer` and `StructuralCavitySliderPocketHostAuthority`.
- **Classification Status**:
  - `CAVITY_SLIDER_HOST_CONFIRMED`: Clear passage aperture verified and isolated from pocket retraction depth; pocket depth sufficiency validated ($D_{\text{pocket}} \ge W_{\text{clear}} - 5.0$ pt); continuous host wall bound.
  - `ABSTAINED_INSUFFICIENT_POCKET_DEPTH`: Pocket depth insufficient for door leaf retraction ($D_{\text{pocket}} < W_{\text{clear}} - 5.0$ pt).
  - `ABSTAINED_DEGENERATE_SPAN`: Clear span $< 20.0$ pt or $> 150.0$ pt.
  - `ABSTAINED_MISALIGNED_POCKET_AXIS`: Pocket mouth-to-back axis deviates from opening axis by $> 0.5^\circ$.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.
