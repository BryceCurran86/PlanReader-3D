# Architecture Report: Source Industrial Sectional Overhead Door Counterweight & High-Lift Track Shadow Authority (v1)

## Executive Summary
Industrial and commercial loading facilities, warehouses, and logistics terminals utilize heavy sectional overhead doors with specialized tracking configurations (standard lift, high lift, vertical lift, or low headroom) balanced by torsion spring counterweight shafts or drum systems and anchored via jamb guide tracks and header brackets.
This report defines the candidate shadow authority for parsing and extracting sectional overhead door track geometry and counterweight details from architectural and structural source plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts such as `SECTIONAL OVERHEAD DOOR`, `HIGH-LIFT TRACK`, `VERTICAL LIFT DOOR`, `TORSION SPRING COUNTERWEIGHT`, `DOOR TRACK BRACKET`, `OVERHEAD SECTIONAL DOOR 4000W X 4500H HIGH LIFT`.
2. **Key Physical Parameters**:
   - `lift_type`: `HIGH_LIFT`, `VERTICAL_LIFT`, `STANDARD_LIFT`, `LOW_HEADROOM`.
   - `door_width_mm`: Extracted horizontal opening width.
   - `door_height_mm`: Extracted vertical opening height.
   - `lift_height_mm`: Additional vertical rise before horizontal break-over.
   - `track_profile`: Track gauge/size, e.g., `50MM (2-INCH)`, `75MM (3-INCH)`.
   - `counterweight_type`: `TORSION_SPRING`, `COUNTERWEIGHT_DRUM`.
3. **Geometric Snapping & Polyline Generation**:
   - Emits track centerline polylines, jamb guide pairs, and clearance boundary envelopes within global 2.5 pt snap tolerance.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Primitive limit: 20,000 max primitives
   - No regression on customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
