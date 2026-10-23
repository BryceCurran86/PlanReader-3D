# Architecture Report: Source Structural Masonry Expansion Joint & Helical Bed Joint Reinforcement Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In clay brickwork, concrete blockwork, cavity walls, and architectural veneers, vertical movement expansion joints and horizontal bed joint reinforcements prevent cracking from differential settlement and thermal expansion.
Masonry takeoffs frequently fail to quantify shear transfer slip dowels in vertical joints or bed reinforcement meters (helical stainless steel wire) embedded along horizontal mortar beds.
This authority extracts vertical movement joints, debonded slip dowels, backing rods, sealant linear meters, and helical bed joint reinforcement runs directly from architectural and structural wall plans.

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
class MasonryMovementJointType(str, Enum):
    VERTICAL_CONTROL_EXPANSION_JOINT = "VERTICAL_CONTROL_EXPANSION_JOINT"
    ARTICULATION_SETTLEMENT_JOINT = "ARTICULATION_SETTLEMENT_JOINT"
    CAVITY_VENEER_EXPANSION_JOINT = "CAVITY_VENEER_EXPANSION_JOINT"

class BedJointReinforcementType(str, Enum):
    HELICAL_STAINLESS_BAR = "HELICAL_STAINLESS_BAR"
    TRUSS_LADDER_WIRE_MESH = "TRUSS_LADDER_WIRE_MESH"
    NO_BED_REINFORCEMENT = "NO_BED_REINFORCEMENT"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for joint width ($W_{joint}$, e.g. 10mm, 15mm, 20mm), slip dowel diameter/spacing (e.g. R12 at 400mm), helical bar diameter (e.g. 6mm, 8mm), and course frequency.
2. **Joint Quantities:**
   - Joint linear meters $L_{joint} = H_{wall}$ per vertical joint location.
   - Slip dowels per joint $N_{dowels} = \lceil H_{wall} / S_{dowel} \rceil$.
3. **Bed Joint Quantities:**
   - $L_{helical} = L_{wall\_run} \times N_{reinforced\_courses}$.
4. **Point Snapping:** Joint coordinates snapped to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_masonry_joint_helical_reinforcement_shadow.py` testing callout regex, snapping, dowel counts, sealant length, bed wire length, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
