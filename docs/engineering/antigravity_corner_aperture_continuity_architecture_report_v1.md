# Architectural Report: Source-Authenticated Structural Corner Aperture & Pier Miter Continuity Shadow Authority

**Document ID**: `docs/engineering/antigravity_corner_aperture_continuity_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Structural Failure on Non-Collinear Corner Apertures
- In existing opening host authorities:
  - `OpeningHostBindingProducer` (`pb_opening_host_binding_authority.py`)
  - `OpeningHostFrameProducer` (`pb_opening_host_frame_authority.py`)
  - `OpeningDimensionAuthority` (`pb_opening_dimension_authority.py`)
  - `OpeningLabelDimensionAuthority` (`pb_opening_label_dimension_authority.py`)
- An aperture is strictly assumed to be a 1D scalar interval $[u_0, u_1]$ projected onto a single planar wall axis $\mathbf{u}$.
- In architectural design, corner openings wrap two orthogonal or angled wall runs meeting at a corner vertex $\mathbf{v}_c$:
  1. **Postless Corner Openings (Butt-Joint Glass / Frameless Miters)**: Continuous structural opening wrapping around the corner without a physical post; supported by cantilevered bond beams/lintels.
  2. **Corner Openings with Structural Posts**: The two opening legs terminate at a shared corner post (e.g. $70 \times 70$ mm or $90 \times 90$ mm column).
- When a corner opening is encountered, existing 1D algorithms fail catastrophically:
  - They attempt to measure the opening as a diagonal chord connecting the two far jambs:
    $$W_{\text{chord}} = \|\mathbf{p}_B - \mathbf{p}_A\| = \sqrt{L_A^2 + L_B^2}$$
    which cuts diagonally across internal room floor space instead of following the building envelope ($L_{\text{girth}} = L_A + L_B$).
  - Or they assign the opening to one host wall and discard the perpendicular leg as an unhosted orphan, corrupting opening takeoff and schedule pairing.

---

## 2. Inferred Engineering Causes

### 2.1 Multi-Leg Composite Aperture Topology
A corner aperture consists of:
1. Two non-parallel wall runs, $\text{Wall}_A$ (axis $\mathbf{u}_A$) and $\text{Wall}_B$ (axis $\mathbf{u}_B$), intersecting at corner vertex $\mathbf{v}_c$.
2. Two terminal jambs:
   - $\mathbf{p}_{\text{jamb}, A}$ on $\text{Wall}_A$ at distance $L_A = \|\mathbf{v}_c - \mathbf{p}_{\text{jamb}, A}\|$.
   - $\mathbf{p}_{\text{jamb}, B}$ on $\text{Wall}_B$ at distance $L_B = \|\mathbf{v}_c - \mathbf{p}_{\text{jamb}, B}\|$.
3. Total physical opening perimeter girth:
   $$L_{\text{total}} = L_A + L_B$$
4. Corner Angle:
   $$\theta = \arccos(\mathbf{u}_A \cdot (-\mathbf{u}_B)) \approx 90^\circ \pm 5^\circ$$

### 2.2 Corner Post Condition
- `POSTLESS_BUTT_JOINT`: No solid structural element at $\mathbf{v}_c$; the clear aperture wraps continuously.
- `STRUCTURAL_CORNER_POST`: A solid structural post of dimension $D_{\text{post}} \in [3.0, 10.0]$ pt ($50$ mm to $150$ mm) is detected at $\mathbf{v}_c$, providing a structural vertical load path.

### 2.3 Dual Host Wall Frame Binding
- Rather than forcing a single host wall ID, a corner opening must maintain dual host binding:
  - `host_wall_a_id`: Parent continuous through-wall for Leg A.
  - `host_wall_b_id`: Parent continuous through-wall for Leg B.
  - Coordinate intervals: $[0, L_A]$ on $\text{Wall}_A$, $[0, L_B]$ on $\text{Wall}_B$.

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_corner_aperture_continuity_authority.py`:
- **Sealed Production & Authority**: `StructuralCornerApertureContinuityProducer` and `StructuralCornerApertureContinuityAuthority`.
- **Classification Status**:
  - `CORNER_APERTURE_CONFIRMED`: Two perpendicular legs validated, corner vertex verified, post condition determined, total girth computed ($L_A + L_B$).
  - `ABSTAINED_NON_ORTHOGONAL_ANGLE`: Corner angle deviates significantly from right angle ($|\theta - 90^\circ| > 15^\circ$).
  - `ABSTAINED_DEGENERATE_LEG`: Either leg length $< 15.0$ pt or $> 300.0$ pt.
  - `ABSTAINED_NON_INTERSECTING_AXES`: Wall axes do not intersect at a valid corner vertex.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.
