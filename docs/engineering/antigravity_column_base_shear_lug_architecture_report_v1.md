# Architecture Report: Source Structural Steel Column Base Grout Key & Shear Lug Shadow Authority (v1)

## Executive Summary
In structural steel framed buildings subject to substantial lateral wind, seismic, or overhead crane runway horizontal braking forces, column base connections must transfer heavy base shear into concrete footings or piers. Where anchor bolts cannot resist the total shear through friction and dowel bearing, a steel shear lug (fabricated from thick plate, structural tee, hollow section, or wide flange stub) is welded to the underside of the baseplate. The lug projects into a formed pocket or box-out (grout key) in the top of the pedestal, which is subsequently filled with high-strength non-shrink cementitious grout.
This report establishes the candidate shadow authority for parsing and extracting column base shear lugs, grout key dimensions, and foundation embedment details from structural steel detail drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `SHEAR LUG`, `GROUT KEY`, `BASEPLATE SHEAR KEY`, `SHEAR KEY RECESS`, `SHEAR KEY BOXOUT`, `BASE PLATE LUG`.
2. **Key Physical Parameters**:
   - `lug_type`: `PLATE_SHEAR_LUG`, `SHS_BOX_LUG`, `UB_SECTION_LUG`, `DOUBLE_ANGLE_LUG`.
   - `lug_section`: Member profile or plate size (e.g. `25MM PL`, `150x150x12 SHS`, `150UB14`).
   - `lug_projection_mm`: Projection depth into concrete (e.g. `75MM`, `100MM`, `150MM`).
   - `grout_key_size_mm`: Box-out width x depth (e.g. `200x200`, `250x250`).
   - `grout_strength_mpa`: Non-shrink grout compressive strength (e.g. `60`, `70`, `80`).
3. **Geometric Snapping & Polyline Representation**:
   - Lug and grout key points and outline polylines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or coordinate span.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
