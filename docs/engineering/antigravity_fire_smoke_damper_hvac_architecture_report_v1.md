# Architecture Report: Source Fire & Smoke Dampers in Ducted Mechanical HVAC Penetration Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In ducted HVAC systems, penetrations through fire-rated barrier walls, smoke-isolated zones, and floor slabs require certified fire dampers (FD), smoke dampers (SD), and motorized combination fire/smoke dampers (FSD).
Mechanical and passive fire takeoffs require explicit quantification of damper dimensions, face flow area ($m^2$), fire ratings (FRL -/120/- or -/240/-), motorized electric spring-return actuators (24V/240V), duct inspection access panels, and bilateral retaining mounting angles.
This authority extracts damper positions, dimensions, mounting types, actuator requirements, and barrier host IDs directly from mechanical HVAC plans and wall penetration schedules.

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
class DamperType(str, Enum):
    MOTORIZED_FIRE_SMOKE_DAMPER = "MOTORIZED_FIRE_SMOKE_DAMPER"
    MECHANICAL_CURTAIN_FIRE_DAMPER = "MECHANICAL_CURTAIN_FIRE_DAMPER"
    MULTI_BLADE_SMOKE_DAMPER = "MULTI_BLADE_SMOKE_DAMPER"
    INTUMESCENT_AIR_TRANSFER_DAMPER = "INTUMESCENT_AIR_TRANSFER_DAMPER"

class ActuatorPowerType(str, Enum):
    ELECTRIC_SPRING_RETURN_24V = "ELECTRIC_SPRING_RETURN_24V"
    ELECTRIC_SPRING_RETURN_240V = "ELECTRIC_SPRING_RETURN_240V"
    THERMAL_FUSIBLE_LINK_ONLY = "THERMAL_FUSIBLE_LINK_ONLY"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for damper typology, duct width and height, FRL rating (-/120/-, -/240/-), actuator voltage (24V/240V), and access panels.
2. **Dimension & Area Calculations:**
   - Face airflow area $A_{face} = (W_{duct} / 1000) \times (H_{duct} / 1000)$.
   - Perimeter retention angles length (two sides of partition): $L_{angles} = 2 \times 2 \times (W_{duct} + H_{duct}) / 1000$.
3. **Point Snapping:** Snaps damper coordinates to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_fire_smoke_damper_hvac_shadow.py` testing callout regex, snapping, face area, retaining angle length, actuator counts, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
