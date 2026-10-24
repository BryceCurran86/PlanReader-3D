# Architecture Report: Source Architectural Expansion Joint Fire Barrier Blanket Shadow Authority (v1)

## Executive Summary
Large commercial developments, airports, hospitals, and educational facilities incorporate structural movement gaps (expansion joints and seismic separations typically 50mm to 200mm wide) passing through fire-rated floor slabs, compartment walls, and ceilings. To maintain mandatory fire compartmentation (1-hour to 4-hour fire ratings), tested expansion joint fire barrier systems comprising ceramic fiber blankets, high-temperature intumescent fabric, and stainless steel retaining flanges are suspended across the joint gap to absorb multi-directional building movement without compromising fire protection.
This report establishes the candidate shadow authority for parsing and extracting expansion joint fire barrier blankets, joint widths, fire ratings, and alignment traces from architectural and fire separation plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `EXPANSION JOINT FIRE BARRIER`, `FIRE BLANKET EXPANSION JOINT`, `FIRE BARRIER BLANKET`, `SEISMIC JOINT FIRE BLANKET`, `CERAMIC FIBER FIRE BARRIER`, `FIRE BLANKET`, `2-HR FIRE BLANKET`.
2. **Key Physical Parameters**:
   - `joint_type`: `FLOOR_EXPANSION_JOINT`, `WALL_EXPANSION_JOINT`, `CEILING_EXPANSION_JOINT`, `ROOF_EXPANSION_JOINT`.
   - `fire_rating_hours`: Fire resistance rating (e.g. `1`, `2`, `3`, `4` hours, or `FRL -/120/120`).
   - `joint_width_mm`: Movement gap width (e.g. `50MM`, `75MM`, `100MM`, `150MM`, `200MM`).
   - `barrier_material`: `CERAMIC_FIBRE_BLANKET`, `INTUMESCENT_FABRIC`, `MINERAL_WOOL_MAT`, `GRAPHITE_COMPOSITE`.
   - `movement_capacity_pct`: Movement tolerance percentage (e.g. `+/- 25%`, `+/- 50%`).
3. **Geometric Snapping & Polyline Representation**:
   - Joint alignment polylines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total joint linear run length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
