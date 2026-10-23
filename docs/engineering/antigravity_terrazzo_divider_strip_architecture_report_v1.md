# Architecture Report: Source Epoxy Terrazzo Floor Divider Strip & Movement Joint Shadow Authority (v1)

## Executive Summary
Architectural interior floor specifications frequently designate epoxy or cementitious terrazzo floor systems with metallic divider strips (brass, zinc, aluminium) creating geometric panel arrays, controlling thermal/shrinkage cracking, and separating colour transitions. In addition, wide flexible neoprene movement joints are placed directly over underlying concrete slab contraction/expansion joints.
This report establishes the candidate shadow authority for parsing and extracting terrazzo divider strip networks, movement joint traces, and module dimensions from architectural finish plans and details.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `TERRAZZO DIVIDER STRIP`, `TERRAZZO MOVEMENT JOINT`, `ZINC DIVIDER STRIP`, `BRASS DIVIDER STRIP`, `EXPANSION DIVIDER STRIP`, `CONTROL STRIP`, `TERRAZZO PATTERN STRIP`.
2. **Key Physical Parameters**:
   - `strip_type`: `DIVIDER_STRIP`, `MOVEMENT_JOINT`, `PERIMETER_EXPANSION_JOINT`, `TRANSITION_STRIP`.
   - `strip_material`: `BRASS`, `ZINC`, `ALUMINIUM`, `NEOPRENE_COMPOSITE`, `STAINLESS_STEEL`.
   - `strip_width_mm`: Strip top width (e.g. `3MM`, `6MM`, `10MM`, `12MM`).
   - `strip_height_mm`: Strip embedment height (e.g. `9.5MM`, `12MM`, `16MM`).
   - `grid_module_mm`: Grid layout pattern (e.g. `1200x1200`).
3. **Geometric Snapping & Polyline Representation**:
   - Strip lines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total strip trace length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
