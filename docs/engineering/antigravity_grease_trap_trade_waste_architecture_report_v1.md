# Architecture Report: Source Commercial Kitchen Grease Trap Interceptor & Trade Waste Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Commercial food premises, restaurants, and catering facilities must comply with trade waste discharge standards via grease interceptor arrestors.
Takeoff requirements encompass nominal liquid volume capacity (e.g. 1000L to 5000L), material construction (in-ground concrete vs polyethylene), gas-tight manhole access covers (Class B vs Class D), trade waste inlet/outlet sizing (DN100/DN150), and trade waste sampling monitoring points.
This authority extracts grease traps, liquid volume capacities, gastight access covers, and trade waste sampling pits directly from hydraulic plumbing and site trade waste plans.

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
class GreaseTrapType(str, Enum):
    IN_GROUND_CONCRETE_INTERCEPTOR = "IN_GROUND_CONCRETE_INTERCEPTOR"
    ABOVE_GROUND_POLY_INTERCEPTOR = "ABOVE_GROUND_POLY_INTERCEPTOR"
    UNDER_SINK_AUTOMATIC_RECOVERY = "UNDER_SINK_AUTOMATIC_RECOVERY"

class AccessCoverLoadClass(str, Enum):
    CLASS_B_GASTIGHT = "CLASS_B_GASTIGHT"
    CLASS_D_HEAVY_DUTY_GASTIGHT = "CLASS_D_HEAVY_DUTY_GASTIGHT"
    LIGHTWEIGHT_PEDESTRIAN = "LIGHTWEIGHT_PEDESTRIAN"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for liquid capacity (e.g. 1000L, 2000L), tank construction, access cover load class (Class B/D), pipe diameter (DN100, DN150), and sampling points.
2. **Dimension & Volume Derivation:**
   - Liquid volume in liters and cubic meters ($V_{m3} = V_{liters} / 1000$).
   - Plan footprint derived from boundary polygon or nominal dimensions.
3. **Point Snapping:** Snaps interceptor centroids to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_grease_trap_trade_waste_shadow.py` testing callout regex, snapping, volume derivation, cover counts, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
