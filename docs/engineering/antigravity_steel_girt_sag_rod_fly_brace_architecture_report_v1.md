# Architecture Report: Source Structural Steel Girt Sag Rod & Fly Bracing Shadow Authority (v1)

## 1. Executive Summary
In structural steel building envelopes, cold-formed C- and Z-sections used as wall girts and roof purlins require intermediate restraint against lateral sag and torsional rotation. Engineers specify sag rods or straps spanning between girts (terminating at eaves struts or foundation ties) and fly braces connecting portal frame rafters or columns to purlin/girt bottom flanges to prevent lateral-torsional buckling under wind uplift or gravity moments. Capturing these secondary structural framing elements is critical for accurate 3D geometry without altering core takeoff baselines.

## 2. Geometry & Extraction Model
- **Component Categories**:
  - `SAG_ROD_SYSTEM`: Tension rod or strap system providing vertical sag resistance.
  - `FLY_BRACE`: Angle strut bracing bottom flange of rafter/column to adjacent purlin/girt.
  - `COMBINED_SAG_FLY`: Integrated girt sag and column fly brace schedule.
- **Section Sizes**:
  - Sag rods: M12, M16 threaded rods or flat galvanized straps (e.g. 25x3 mm).
  - Fly braces: Equal angles (e.g. 50x50x5 EA, 50x50x6 EA) or unequal angles (65x50x5 UA).
- **Restraint Spacing**: Midspan (single row), third points (double row), or quarter points.
- **Connection Hardware**: High-tensile or commercial bolts (M12 4.6/S, M16 8.8/S) through pre-punched web holes or welded cleats.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
