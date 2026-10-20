# Architecture Report: Source Raised Access Floor Airflow Grille & Dampened Grommet Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In mission-critical data centers, computer rooms, and commercial tech facilities, raised access floor (RAF) systems manage underfloor pressurized air plenums and cable routing.
Perforated airflow panels, directional cast grilles, volume dampers, and air-seal brush grommets are frequently omitted or miscategorized in structural architectural floor takeoffs.
This authority extracts and categorizes RAF airflow panels, percentage open areas, CFM ratings, damper types, and cable grommets directly from access floor layout plans.

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
class RAFAppurtenanceType(str, Enum):
    PERFORATED_AIRFLOW_PANEL = "PERFORATED_AIRFLOW_PANEL"
    HIGH_CFM_DIRECTIONAL_GRILLE = "HIGH_CFM_DIRECTIONAL_GRILLE"
    INTEGRATED_DAMPER_PANEL = "INTEGRATED_DAMPER_PANEL"
    BRUSH_SEAL_CABLE_GROMMET = "BRUSH_SEAL_CABLE_GROMMET"
    INTEGRAL_FLOOR_BOX = "INTEGRAL_FLOOR_BOX"

class DamperControlMechanism(str, Enum):
    OPPOSING_BLADE_DAMPER = "OPPOSING_BLADE_DAMPER"
    MANUAL_SLIDE_DAMPER = "MANUAL_SLIDE_DAMPER"
    NO_DAMPER = "NO_DAMPER"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for open area percentage (e.g. 25%, 56%, 68%), airflow CFM rating, damper mechanisms, and grommet types.
2. **Point Snapping:** Snaps component centroids to `2.5 pt` tolerance.
3. **Takeoff Aggregation:** Summarizes airflow panel counts, total CFM air capacity, grommet counts, and open area distribution.

## 5. Verification Plan
- Unit test suite: `tests/test_source_raf_airflow_grille_grommet_shadow.py` testing callout regex, snapping, component aggregation, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
