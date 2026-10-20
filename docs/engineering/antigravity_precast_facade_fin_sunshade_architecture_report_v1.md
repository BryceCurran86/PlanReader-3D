# Architecture Report: Source Precast Architectural Facade Feature Fin & Sunshade Louver Shadow Authority (v1)

## Executive Summary
Architectural building envelopes frequently specify vertical or horizontal facade feature fins, aerofoil solar shading louvers, and architectural sunshades fabricated from precast concrete, ultra-high performance concrete (UHPC), or extruded aluminium. These assemblies are tied back to structural slabs or spandrels with stainless steel or hot-dip galvanized cleats.
This report establishes the candidate shadow authority for parsing and extracting architectural feature fin and sunshade louver geometry from facade elevations and architectural plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `ARCHITECTURAL FIN`, `PRECAST FIN`, `SUNSHADE LOUVER`, `SOLAR BLADE`, `FACADE FIN`, `VERTICAL FEATURE FIN`, `HORIZONTAL SUNSHADE`, `AEROFOIL BLADE`.
2. **Key Physical Parameters**:
   - `fin_type`: `VERTICAL_FIN`, `HORIZONTAL_SUNSHADE`, `AEROFOIL_LOUVER`, `SOLID_BLADE`.
   - `material`: `PRECAST_CONCRETE`, `EXTRUDED_ALUMINIUM`, `UHPC`, `GRP`.
   - `fin_width_mm`: Width / thickness of fin.
   - `fin_depth_mm`: Projection / depth of fin.
   - `fin_spacing_mm`: Center-to-center spacing along facade.
   - `blade_angle_deg`: Solar tilt angle in degrees.
3. **Geometric Snapping & Polyline Representation**:
   - Fin axes and centerlines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Calculates total fin length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
