# Architecture Report: Source Structural Steel Crane Runway End Stop & Buffer Shadow Authority (v1)

## Executive Summary
Heavy industrial overhead travelling crane installations require dedicated physical travel limits and energy absorption assemblies at the ends of crane runway girders. Crane runway end stops comprise thick fabricated steel stop brackets welded or bolted to the top flange and rail, fitted with cellular polyurethane, hydraulic, or coil spring buffers designed to absorb the kinetic energy of a fully loaded crane moving at rated speed.
This report establishes the candidate shadow authority for parsing and extracting crane runway end stop brackets, buffer specifications, and mounting geometry from structural crane engineering drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `CRANE END STOP`, `RUNWAY END STOP`, `CRANE BUFFER`, `TRAVEL STOP`, `HYDRAULIC BUFFER`, `POLYURETHANE BUFFER`, `RUNWAY STOP BRACKET`.
2. **Key Physical Parameters**:
   - `stop_type`: `BOLTED_END_STOP`, `WELDED_END_STOP`, `RUNWAY_TRAVEL_STOP`.
   - `buffer_type`: `POLYURETHANE_CELLULAR`, `HYDRAULIC`, `COIL_SPRING`, `RUBBER_BUMPER`.
   - `plate_thickness_mm`: Stop plate thickness (e.g. `16MM`, `20MM`, `25MM`, `32MM`).
   - `crane_capacity_tonnes`: Crane load rating (e.g. `5T`, `10T`, `20T`, `32T`).
   - `buffer_diameter_mm`: Buffer element diameter (e.g. `100MM`, `125MM`, `160MM`, `200MM`).
3. **Geometric Snapping & Polyline Representation**:
   - Point locations and bracket lines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or bracket length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
