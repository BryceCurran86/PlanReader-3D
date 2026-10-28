# Architectural Report: Source-Authenticated Structural Infill Spandrel Wall & Window Sub-Sill Continuity Authority

**Document ID**: `docs/engineering/antigravity_spandrel_sub_sill_continuity_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Window Obliteration by Sub-Sill Spandrel Linework
- In architectural and structural floor plans:
  - Windows in masonry, concrete, or framed walls do not span floor-to-ceiling; they sit above an infill spandrel wall (sub-sill dwarf wall / knee wall) of height $h_{\text{sill}} \approx 600$–$1000$ mm (typically $900$ mm).
  - On 2D plans cut at horizontal cutting plane $h \approx 1000$–$1200$ mm:
    - Drafting packages depict the sub-sill spandrel wall as solid line work beneath the window glazing strokes.
    - Naive 2D tracing routines encounter this solid sub-sill linework and mistake it for unbroken full-height wall continuity, erroneously concluding that no window opening exists and obliterating the window candidate.
    - In reverse errors, if an algorithm ignores the sub-sill wall, it fails to quantify the masonry or framed wall area beneath the sill ($A_{\text{spandrel}} = W_{\text{clear}} \times h_{\text{sill}}$) in wall takeoff quantities.

---

## 2. Inferred Engineering Causes

### 2.1 Spatial Separation between Glazed Aperture and Infill Spandrel
In architectural engineering:
1. **Sub-Sill Spandrel Infill Zone** ($h \in [0, h_{\text{sill}}]$):
   - Solid wall structure supporting the window sill frame and transferring lateral wind loads to the floor slab / subfloor plate.
   - Surface area: $A_{\text{spandrel}} = W_{\text{clear}} \times h_{\text{sill}}$.
2. **Glazed Clear Aperture Zone** ($h \in [h_{\text{sill}}, h_{\text{head}}]$):
   - Physical transparent window aperture cut through the building envelope.
   - Surface area: $A_{\text{glazing}} = W_{\text{clear}} \times (h_{\text{head}} - h_{\text{sill}})$.
3. The authority must authenticate the window aperture without permitting the sub-sill line work to obliterate the opening, while accurately computing both the glazed aperture area and the sub-sill wall area.

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_spandrel_sub_sill_continuity_authority.py`:
- **Sealed Production & Authority**: `StructuralSpandrelSubSillContinuityProducer` and `StructuralSpandrelSubSillContinuityAuthority`.
- **Classification Status**:
  - `SPANDREL_SUB_SILL_CONFIRMED`: Window aperture validated without obliteration by sub-sill spandrel linework; dual areas quantified.
  - `ABSTAINED_INVALID_LEVELS`: $h_{\text{sill}} \ge h_{\text{head}}$ or $h_{\text{head}} \le 0$.
  - `ABSTAINED_DEGENERATE_SPAN`: Clear span $< 20.0$ pt or $> 300.0$ pt.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.
