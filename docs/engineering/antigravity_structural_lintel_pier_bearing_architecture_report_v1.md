# Architectural Report: Source-Authenticated Structural Lintel-to-Pier Bearing & Head Wall Vertical Continuity Authority

**Document ID**: `docs/engineering/antigravity_structural_lintel_pier_bearing_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Aperture Span Inflation by Overhead Lintel Projection
- In structural and architectural drawings:
  - Every door and window opening through loadbearing masonry, precast concrete, or timber/steel framed walls requires an overhead structural lintel (steel angle, parallel flange channel [PFC], reinforced concrete beam, or laminated veneer lumber [LVL] header).
  - Building codes (AS 4773, AS 1684, NCC) mandate minimum structural bearing onto the flanking solid wall piers:
    $$L_{\text{bearing, left}} \ge 100\text{ mm},\quad L_{\text{bearing, right}} \ge 100\text{ mm}$$
    ($\approx 5.67$ pt at 1:100 scale).
  - The total manufactured lintel length is therefore:
    $$L_{\text{lintel}} = W_{\text{clear}} + L_{\text{bearing, left}} + L_{\text{bearing, right}} \approx W_{\text{clear}} + 200\text{ mm to } 300\text{ mm}$$
- The Failure in Unauthenticated Vector Tracing:
  - On floor plans and reflected framing plans, lintels are depicted as dashed/hidden overhead lines extending past the clear opening jambs into the flanking wall piers.
  - Naive opening detectors mistake the dashed lintel extents for the clear opening aperture, falsely inflating the window/door width by $200$–$300$ mm ($11.3$–$17.0$ pt).
  - Consequently:
    1. The inflated opening fails schedule correspondence because the nominal schedule size (e.g. $1800$ mm) does not match the inflated $2000$ mm vector span.
    2. The flanking solid piers are artificially truncated by the bearing depth, triggering false minimum-pier-width failures in wall continuity authorities.
  - In section/elevation linkages, lintel specifications (e.g. `200 PFC LINTEL`, `2/240x45 LVL 15`) remain disconnected from the physical opening load path.

---

## 2. Inferred Engineering Causes

### 2.1 Cutting Plane vs Overhead Framing Separation
In architectural CAD standards:
1. **Plan Cutting Plane** ($h \approx 1000$–$1200$ mm): Cuts through wall masonry, timber studs, and window/door glazed frames. Rendered with solid strokes.
2. **Overhead Structural Projection** ($h \approx 2100$–$2700$ mm): Sits above the opening head. Lintels, drop beams, and bulkheads are rendered as dashed lines (`dash_pattern != None`) or placed on designated structural framing layers.
3. Algorithms that collapse all line layers without discriminating stroke style or z-elevation falsely fuse overhead lintel overhangs into the plan-view aperture void.

### 2.2 Pier Bearing Structural Mechanics
- A lintel transfers gravity loads from roof trusses, floor joists, and upper masonry down to the foundations via the flanking wall piers.
- Minimum bearing seat: $L_{\text{bearing}} \ge 100$ mm ($5.67$ pt at 1:100).
- Flanking pier width must satisfy $W_{\text{pier}} \ge L_{\text{bearing}}$.

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_lintel_pier_bearing_authority.py`:
- **Sealed Production & Authority**: `StructuralLintelPierBearingProducer` and `StructuralLintelPierBearingAuthority`.
- **Classification Status**:
  - `LINTEL_BEARING_CONFIRMED`: Clear span isolated from lintel overhang; compliant bearing seats ($\ge 100$ mm) verified on flanking host piers.
  - `ABSTAINED_INSUFFICIENT_BEARING`: Flanking pier width or bearing length $< 100$ mm ($5.67$ pt at 1:100).
  - `ABSTAINED_LINTEL_SPURIOUS_OVERHANG`: Overhang exceeds maximum allowable structural projection ($> 300$ mm).
  - `ABSTAINED_MISSING_HOST_PIER`: No solid wall pier flanking the terminal jamb.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.
