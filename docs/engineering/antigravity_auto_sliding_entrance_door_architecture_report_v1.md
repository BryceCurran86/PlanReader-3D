# Architecture Report: Source Automatic Sliding & Telescopic Sensor Entrance Door Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In commercial lobbies, transport terminals, healthcare hubs, and retail shopping centers, automatic sliding entrance doors constitute high-value specialty architectural assemblies.
Takeoffs require separating total framing width (including fixed pocket sidelites) from clear opening walk-through width, active leaf count, operator header transom beam, microwave motion sensors, and safety pocket barrier screens.
This authority extracts and structures automatic entrance door geometries, opening schedules, clear width metrics, and safety barrier rails directly from architectural door schedules and wall opening vectors.

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
class AutomaticDoorType(str, Enum):
    BI_PARTING_SLIDING_DOOR = "BI_PARTING_SLIDING_DOOR"
    SINGLE_SLIDE_DOOR = "SINGLE_SLIDE_DOOR"
    TELESCOPIC_SLIDING_DOOR = "TELESCOPIC_SLIDING_DOOR"
    AUTOMATIC_REVOLVING_DOOR = "AUTOMATIC_REVOLVING_DOOR"
    AUTOMATIC_SWING_OPERATOR = "AUTOMATIC_SWING_OPERATOR"

class ActivationSensorType(str, Enum):
    RADAR_MICROWAVE_AND_IR = "RADAR_MICROWAVE_AND_IR"
    PUSH_PAD_ACTUATOR = "PUSH_PAD_ACTUATOR"
    ACCESS_CONTROL_READER = "ACCESS_CONTROL_READER"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for door typology, clear opening width and height, frame width, sensor configurations, and barrier screens.
2. **Dimension Derivation:**
   - For bi-parting sliders: $W_{frame} \approx 2 \times W_{clear} + 100\text{mm}$ (if not explicitly given).
   - For single sliders: $W_{frame} \approx 2 \times W_{clear}$.
   - Clear opening area $A_{clear} = W_{clear} \times H_{clear}$.
   - Overall frame elevation area $A_{frame} = W_{frame} \times H_{frame}$.
3. **Point Snapping:** Opening centerpoint and frame vertices snapped to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_auto_sliding_entrance_door_shadow.py` testing callout regex, snapping, clear vs frame dimensions, barrier screens, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
