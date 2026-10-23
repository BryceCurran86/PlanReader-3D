# Architecture Report: Source Overhead Coiling Fire Shutter & Smoke Baffle Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Compartmentation in retail arcades, warehouse openings, carpark portals, and atriums requires motorized coiling fire shutters and smoke containment curtains.
Accurate takeoff requires distinguishing clear walkthrough dimensions from total shutter curtain fabric/slat area, overhead barrel hood enclosures, structural side guide tracks, and release mechanisms (fusible link vs fire alarm signal).
This authority extracts and structures overhead coiling fire shutters, smoke curtains, hood dimensions, side guide tracks, and FRL ratings directly from architectural door schedules and opening geometry.

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
class FireShutterType(str, Enum):
    MOTORIZED_FIRE_COILING_SHUTTER = "MOTORIZED_FIRE_COILING_SHUTTER"
    SMOKE_CONTAINMENT_CURTAIN = "SMOKE_CONTAINMENT_CURTAIN"
    OVERHEAD_SECTIONAL_INSULATED_DOOR = "OVERHEAD_SECTIONAL_INSULATED_DOOR"
    COUNTER_FIRE_SHUTTER = "COUNTER_FIRE_SHUTTER"

class ShutterReleaseMechanism(str, Enum):
    FIRE_ALARM_SIGNAL_DROP = "FIRE_ALARM_SIGNAL_DROP"
    FUSIBLE_LINK_GRAVITY_DROP = "FUSIBLE_LINK_GRAVITY_DROP"
    MANUAL_CHAIN_HOIST = "MANUAL_CHAIN_HOIST"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for shutter typology, clear opening width and height, FRL fire rating (-/120/-, -/240/-), hood dimension, and release mechanism.
2. **Dimension & Area Calculations:**
   - Clear opening area $A_{clear} = W_{clear} \times H_{clear}$.
   - Overall curtain area $A_{curtain} = (W_{clear} + 2 \times W_{guide}) \times (H_{clear} + H_{hood})$.
   - Side guide track linear meters $L_{guide} = 2 \times H_{clear}$.
   - Barrel hood length $L_{hood} = W_{clear} + 2 \times W_{guide}$.
3. **Point Snapping:** Snaps opening centroids to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_fire_shutter_smoke_baffle_shadow.py` testing callout regex, snapping, clear vs curtain area, guide track length, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
