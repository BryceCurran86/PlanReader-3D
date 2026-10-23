# Architecture Report: Source Heavy-Duty Trench Drain & Cast Iron Grate Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Civil surface drainage, basement carparks, commercial driveways, and industrial loading aprons rely on linear trench drains with load-rated grating to capture runoff.
Takeoffs must separate trench channel widths (100mm, 150mm, 200mm, 300mm), grating load classifications (Class B, C, D, E per AS 3996 / EN 1433), concrete haunch/bedding encasement volumes, and in-line silt basket pits.
This authority extracts trench drain centerlines, widths, depths, grate types, and sump pit accessories directly from civil and hydraulic stormwater plans.

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
class TrenchGrateType(str, Enum):
    DUCTILE_IRON_SLOTTED_GRATE = "DUCTILE_IRON_SLOTTED_GRATE"
    HEELGUARD_STAINLESS_WEDGE_WIRE = "HEELGUARD_STAINLESS_WEDGE_WIRE"
    GALVANIZED_STEEL_BAR_GRATE = "GALVANIZED_STEEL_BAR_GRATE"
    SOLID_DUCTILE_IRON_COVER = "SOLID_DUCTILE_IRON_COVER"

class TrenchLoadClass(str, Enum):
    CLASS_B_LIGHT_TRAFFIC = "CLASS_B_LIGHT_TRAFFIC"
    CLASS_C_COMMERCIAL = "CLASS_C_COMMERCIAL"
    CLASS_D_HEAVY_DUTY = "CLASS_D_HEAVY_DUTY"
    CLASS_E_INDUSTRIAL = "CLASS_E_INDUSTRIAL"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for trench internal width ($W_{int}$, e.g. 100mm, 150mm, 200mm), grate type, load class (Class B/C/D/E), depth, and silt baskets.
2. **Polyline Snapping & Length:** Centerline snapping with $2.5\text{ pt}$ tolerance, evaluating exact linear meters of trench runs.
3. **Concrete Surround Volume:**
   - Concrete bed and haunch encasement: $W_{ext} = W_{int} + 2 \times 150\text{mm}$, $D_{ext} = D_{int} + 150\text{mm}$.
   - $V_{concrete} = L \times (W_{ext} \times D_{ext} - W_{int} \times D_{int})$.

## 5. Verification Plan
- Unit test suite: `tests/test_source_trench_drain_grate_shadow.py` testing callout regex, snapping, linear meters, concrete surround volume, sump pits, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
