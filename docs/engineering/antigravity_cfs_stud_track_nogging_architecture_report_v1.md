# Architecture Report: Source Structural Cold-Formed Steel Stud Wall Track & Nogging Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In lightweight commercial partitioning, drywall envelopes, and external curtain framing, cold-formed steel (CFS) light-gauge framing forms the primary structural substrate.
Takeoffs must resolve not only wall surface area, but structural member line items: top deflection track, bottom runner track, vertical C-studs (spaced at 450/600mm centers), and horizontal nogging/bridging rows.
This shadow authority extracts wall path alignments, stud depth and thickness, top/bottom track linear meters, nogging rows, and stud counts directly from partition schedules and wall layout lines.

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
class CFSFramingType(str, Enum):
    INTERNAL_NON_LOADBEARING_STUD = "INTERNAL_NON_LOADBEARING_STUD"
    STRUCTURAL_LOADBEARING_CFS_STUD = "STRUCTURAL_LOADBEARING_CFS_STUD"
    ACOUSTIC_STAGGERED_STUD = "ACOUSTIC_STAGGERED_STUD"
    SHAFTWALL_CH_STUD = "SHAFTWALL_CH_STUD"

class HeadTrackType(str, Enum):
    SLOTTED_DEFLECTION_TRACK = "SLOTTED_DEFLECTION_TRACK"
    STANDARD_DEEP_LEG_TRACK = "STANDARD_DEEP_LEG_TRACK"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for stud width (64mm, 76mm, 92mm, 150mm), BMT (0.50mm, 0.75mm, 1.15mm), stud spacing (400mm, 450mm, 600mm), head track type, and nogging rows.
2. **Polyline Snapping & Wall Length:** Centerline snapping with $2.5\text{ pt}$ tolerance, evaluating exact linear meters of wall framing.
3. **Framing Quantities:**
   - Top & bottom track linear meters: $2 \times L$
   - Stud counts: $N_{studs} = \lceil L / S_{stud} \rceil + 1$
   - Nogging linear meters: $L \times N_{noggings}$
   - Total vertical stud linear meters: $N_{studs} \times H_{wall}$.

## 5. Verification Plan
- Unit test suite: `tests/test_source_cfs_stud_track_nogging_shadow.py` testing callout regex, snapping, track length, nogging length, stud counts, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
