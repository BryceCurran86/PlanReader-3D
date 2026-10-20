# Architecture Report: Source Structural Steel Crane Runway Girders & Rail Assembly Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Heavy industrial buildings, engineering fabrication facilities, and steel distribution hubs feature overhead bridge cranes supported by dedicated crane runway girders and precision rail tracks.
Structural steel takeoffs must capture not only the primary girder sections (e.g. 610UB125, 700WB150, or plate girders) but also crane rail sections (CR50, CR60, 50kg/m rail), resilient elastomeric bedding pads, adjustable rail clips, and crane buffer end stops.
This authority extracts runway beam alignments, rail profiles, mounting clip counts, and buffer hardware directly from structural framing plans.

## 2. Invariants & Non-Negotiables
- **Customer Retention Invariance:** Must strictly preserve the baseline fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`) across all test suites.
- **Strict Evaluator Separation:** Zero project-specific heuristics or hardcoding.
- **Safety Cap & Snap Tolerance:** Coordinate snapping strictly aligned to `SNAP_TOLERANCE_PT = 2.5`.
- **Shadow Mode Isolation:**
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`

## 3. Typology & Data Contracts
```python
class CraneRunwayType(str, Enum):
    OVERHEAD_BRIDGE_CRANE_RUNWAY = "OVERHEAD_BRIDGE_CRANE_RUNWAY"
    MONORAIL_HOIST_BEAM = "MONORAIL_HOIST_BEAM"
    GANTRY_PORTAL_RAIL = "GANTRY_PORTAL_RAIL"
    WALL_JIB_CRANE_TRACK = "WALL_JIB_CRANE_TRACK"

class CraneRailMountingType(str, Enum):
    RESILIENT_ELASTOMERIC_PAD = "RESILIENT_ELASTOMERIC_PAD"
    DIRECT_STEEL_BEARING = "DIRECT_STEEL_BEARING"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for girder size (UB/WB/PFC), rail section (CR50, CR60, 50kg/m), clip spacing (e.g. 600mm), and buffer end stops.
2. **Polyline Snapping & Length:** Centerline snapping with $2.5\text{ pt}$ tolerance, evaluating exact linear meters of runway girders and rails.
3. **Component Quantities:**
   - $N_{clips} = 2 \times (\lceil L / S_{clip} \rceil + 1)$ (pairs on both sides of rail flange)
   - $N_{buffers} = 2$ per runway line
   - Resilient pad linear meters = rail linear meters.

## 5. Verification Plan
- Unit test suite: `tests/test_source_crane_runway_girder_rail_shadow.py` testing callout regex, snapping, girder length, rail clips count, buffers count, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
