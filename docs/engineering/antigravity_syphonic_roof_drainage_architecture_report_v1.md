# Architecture Report: Source Roof Syphonic Rainwater Drainage Bowl & Tailpipe Tail Shadow Authority (v1)

## Executive Summary
Large footprint commercial roofs and industrial warehouses employ engineered syphonic rainwater drainage systems. Syphonic systems operate with water-filled pipes under negative pressure induced by anti-vortex air baffle outlet bowls, vertical tailpipes, and flat horizontal high-density polyethylene (HDPE) collectors.
This report defines the candidate shadow authority for parsing and extracting syphonic drainage components, bowl coordinates, and pipe runs from hydraulic and plumbing drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `SYPHONIC DRAINAGE`, `SIPHONIC DRAIN`, `SYPHONIC BOWL`, `ROOF DRAIN BOWL`, `TAILPIPE`, `HDPE COLLECTOR`, `AIR BAFFLE BOWL`.
2. **Key Physical Parameters**:
   - `component_type`: `ROOF_OUTLET_BOWL`, `TAILPIPE`, `HORIZONTAL_COLLECTOR`, `OVERFLOW_OUTLET`.
   - `diameter_dn_mm`: Nominal diameter (e.g. `DN75`, `DN110`, `DN160`, `DN200`).
   - `pipe_material`: `HDPE`, `CAST_IRON`, `STAINLESS_STEEL`.
   - `has_air_baffle`: True if anti-vortex plate/baffle specified.
   - `leaf_guard_type`: `DOME_GRATE`, `FLAT_GRATE`.
3. **Geometric Snapping & Polyline Representation**:
   - Outlet points snapped to `SNAP_TOLERANCE_PT = 2.5` pt.
   - Tailpipe / collector polylines snapped and measured.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
