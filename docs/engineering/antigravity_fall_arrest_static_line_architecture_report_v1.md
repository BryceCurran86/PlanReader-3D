# Architecture Report: Source Roof Fall Arrest Static Safety Line & Anchor Point Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Roof safety access, plant maintenance, and height safety regulations demand certified fall arrest systems, including horizontal cable lifelines, intermediate pass-through brackets, tensioners, inline shock absorbers, and abseil rope access anchor points.
Takeoffs require differentiating horizontal continuous static cables from discrete anchor points, substrate fixings (metal deck purlin, structural steel, concrete cast-in), load ratings (15 kN fall arrest vs 22 kN rope access), and specialized shock absorber hardware.
This authority extracts and quantifies static line cable runs, intermediate posts, single/twin anchor points, and shock absorbers directly from height safety roof plans.

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
class FallProtectionType(str, Enum):
    HORIZONTAL_STATIC_LIFELINE = "HORIZONTAL_STATIC_LIFELINE"
    SINGLE_POINT_FALL_ARREST_ANCHOR = "SINGLE_POINT_FALL_ARREST_ANCHOR"
    ROPE_ACCESS_ABSEIL_ANCHOR = "ROPE_ACCESS_ABSEIL_ANCHOR"
    RIGID_RAIL_FALL_SYSTEM = "RIGID_RAIL_FALL_SYSTEM"

class AnchorMountingSubstrate(str, Enum):
    PURLIN_METAL_DECK_MOUNT = "PURLIN_METAL_DECK_MOUNT"
    CONCRETE_STRUCTURE_MOUNT = "CONCRETE_STRUCTURE_MOUNT"
    STEEL_BEAM_CLAMP_MOUNT = "STEEL_BEAM_CLAMP_MOUNT"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for cable diameter (e.g. 8mm), rating (15 kN, 22 kN), intermediate spacing (e.g. 8.0m), shock absorbers, and substrate type.
2. **Polyline Snapping & Cable Takeoff:** Centerline snapping with $2.5\text{ pt}$ tolerance, evaluating exact linear meters of cable runs.
3. **Hardware Count Estimation:**
   - Intermediate brackets $N_{int} = \max(0, \lceil L / S_{int} \rceil - 1)$
   - End anchor posts $N_{end} = 2$ per static line run.
   - Energy absorbers count per run.

## 5. Verification Plan
- Unit test suite: `tests/test_source_fall_arrest_static_line_anchor_shadow.py` testing callout regex, snapping, cable length, intermediate brackets, anchors, shock absorbers, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
