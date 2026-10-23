# Architecture Report: Source Fire Hose Reel & Dry/Wet Riser Booster Landing Valve Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Fire hose reels (FHR) and wet/dry riser landing valves are critical life safety equipment installed in fire egress stairs, corridors, and exterior staging areas.
Commercial mechanical/fire takeoffs must isolate mounting cabinet types (recessed vs surface), hose specifications (36m x 19mm/25mm), isolation valves (DN25), and landing valve diameters (DN65) without hardcoding or ungrounded heuristics.
This authority extracts and categorizes fire hose reels, booster landing valves, and breeching connections directly from fire service plans.

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
class FireApparatusType(str, Enum):
    FIXED_FIRE_HOSE_REEL = "FIXED_FIRE_HOSE_REEL"
    SWINGING_ARM_FIRE_HOSE_REEL = "SWINGING_ARM_FIRE_HOSE_REEL"
    WET_RISER_LANDING_VALVE = "WET_RISER_LANDING_VALVE"
    DRY_RISER_LANDING_VALVE = "DRY_RISER_LANDING_VALVE"
    EXTERNAL_BREECHING_INLET = "EXTERNAL_BREECHING_INLET"

class MountingEnclosureType(str, Enum):
    RECESSED_WALL_CABINET = "RECESSED_WALL_CABINET"
    SURFACE_MOUNTED_CABINET = "SURFACE_MOUNTED_CABINET"
    OPEN_WALL_BRACKET = "OPEN_WALL_BRACKET"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for apparatus type, mounting cabinet style, hose length and diameter (e.g. 36m x 19mm), valve size (DN25 / DN65), and breeching inlets (2-way / 4-way).
2. **Point Snapping:** Snaps apparatus coordinates to `2.5 pt` tolerance.
3. **Takeoff Aggregation:** Groups counts by equipment type and mounting style.

## 5. Verification Plan
- Unit test suite: `tests/test_source_fire_hose_reel_booster_riser_shadow.py` testing callout regex, snapping, component aggregation, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
