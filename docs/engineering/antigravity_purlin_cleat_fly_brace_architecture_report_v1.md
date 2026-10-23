# Architecture Report: Source Structural Steel Purlin Cleat & Fly Bracing Connection Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In industrial portal frame steel structures, roof purlins and wall girts connect to portal rafters and columns via welded/bolted purlin cleats.
Crucially, bottom-flange torsional buckling restraint for rafters requires diagonal fly bracing connected between purlins and rafter bottom flanges.
Failure to quantify cleats, bolts, and fly braces produces major steel tonnage and connection hardware shortfalls.
This authority extracts purlin cleats, bolt assemblies, fly brace angles, and diagonal lengths directly from structural rafter detail plans.

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
class PurlinCleatType(str, Enum):
    STANDARD_ANGLE_CLEAT = "STANDARD_ANGLE_CLEAT"
    FORMED_PLATE_CLEAT = "FORMED_PLATE_CLEAT"
    CONTINUOUS_LAP_CLEAT = "CONTINUOUS_LAP_CLEAT"

class FlyBracingType(str, Enum):
    SINGLE_ANGLE_FLY_BRACE = "SINGLE_ANGLE_FLY_BRACE"
    DOUBLE_ANGLE_FLY_BRACE = "DOUBLE_ANGLE_FLY_BRACE"
    NO_FLY_BRACE = "NO_FLY_BRACE"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for purlin section (Z150, Z200, Z250), cleat size, bolt count/size (M12, M16), and fly brace equal angle profiles (e.g. 50x50x5 EA).
2. **Component Quantities:**
   - Cleat counts, bolt counts ($N_{cleats} \times N_{bolts\_per\_cleat}$).
   - Fly brace counts and diagonal steel length ($L_{diag} \approx \sqrt{H_{rafter}^2 + S_{purlin}^2}$ or explicit callout).
3. **Point Snapping:** Snaps rafter connection node coordinates to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_purlin_cleat_fly_brace_shadow.py` testing callout regex, snapping, cleat and fly brace counts, bolt counts, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
