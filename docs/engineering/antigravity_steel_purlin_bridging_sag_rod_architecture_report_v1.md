# Architecture Report: Source Structural Steel Purlin Bridging & Sag Rod Tension Tie Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In industrial portal frames and structural steel roof framing, roof purlins and wall girts require lateral and torsional restraint provided by bridging lines, sag rods, apex ties, and turnbuckles.
Without explicit shadow quantification of bridging components, structural takeoffs suffer from missing steel hardware and erroneous framing erection estimates.
This authority extracts purlin bridging alignments, sag rod tension ties, apex connections, and component counts directly from framing plans and roof structural schedules.

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
class PurlinBridgingType(str, Enum):
    SOLID_BRIDGING_STRUT = "SOLID_BRIDGING_STRUT"
    SAG_ROD_TENSION_TIE = "SAG_ROD_TENSION_TIE"
    APEX_BRIDGING_SYSTEM = "APEX_BRIDGING_SYSTEM"
    FASCIA_DIAGONAL_BRACE = "FASCIA_DIAGONAL_BRACE"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Robust regex parsing for bridging profile (e.g. PB150, PB200), sag rod diameter (M12, M16), number of bridging lines (midspan vs. third-point), and apex hardware.
2. **Polyline Snapping & Length:** Centerline snapping with $2.5\text{ pt}$ tolerance, evaluating exact linear meters of bridging lines.
3. **Component Count Estimation:** Derives number of purlin intersections, sag rods, and turnbuckles based on purlin spacing and line length.

## 5. Verification Plan
- Unit test suite: `tests/test_source_steel_purlin_bridging_sag_rod_shadow.py` testing callout regex, snapping, line length, component counts, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
