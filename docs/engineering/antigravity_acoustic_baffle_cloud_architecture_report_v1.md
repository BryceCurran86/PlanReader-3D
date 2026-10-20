# Architecture Report: Source Commercial Architectural Acoustic Ceiling Baffle & Raft Cloud Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In modern exposed-soffit architectural designs, suspended vertical acoustic baffles and horizontal ceiling clouds/rafts provide sound reverberation control without continuous suspended plasterboard ceilings.
Reflective ceiling plan (RCP) takeoffs require calculating both linear extrusion meters and effective dual-faced absorption surface area ($m^2$), acoustic rating (NRC), baffle blade counts, and wire rope suspension points.
This shadow authority extracts ceiling acoustic baffle arrays, cloud rafts, spacing intervals, NRC performance metrics, and suspension drops directly from reflected ceiling plans.

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
class AcousticCeilingType(str, Enum):
    VERTICAL_SUSPENDED_BAFFLE = "VERTICAL_SUSPENDED_BAFFLE"
    HORIZONTAL_RAFT_CLOUD = "HORIZONTAL_RAFT_CLOUD"
    TIMBER_SLATTED_BAFFLE = "TIMBER_SLATTED_BAFFLE"
    DIRECT_FIX_ACOUSTIC_TILE = "DIRECT_FIX_ACOUSTIC_TILE"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for baffle thickness and depth (e.g. 50x200mm), center-to-center spacing ($S_{baffle}$), NRC rating (e.g. 0.85), and cloud panel dimensions (e.g. 2400x1200mm).
2. **Dimension & Area Calculations:**
   - Linear baffle run length: $L_{run}$.
   - Vertical baffle dual-side acoustic absorption area: $A_{abs} = 2 \times (H_{depth} / 1000) \times L_{run}$.
   - Horizontal cloud absorption area: $A_{abs} = (W / 1000) \times (L / 1000)$.
   - Suspension wire drop count: $N_{wires} = 2 \times \lceil L_{run} / 1.5\text{m} \rceil$.
3. **Point Snapping:** Snaps run vertices to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_acoustic_baffle_cloud_shadow.py` testing callout regex, snapping, linear meters, absorption area, suspension wire drops, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
