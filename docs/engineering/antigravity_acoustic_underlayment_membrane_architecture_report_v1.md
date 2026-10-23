# Architecture Report: Source Acoustic Underlayment & Resilient Flooring Isolation Membrane Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Impact acoustic performance in residential and commercial buildings relies heavily on resilient underlayment membranes and perimeter flanking isolation strips to decouple finished floors from structural slabs.
Missing or poorly typed underlayments lead to severe acoustic compliance failure and major commercial cost variances.
This shadow authority extracts and quantifies acoustic membranes, thicknesses, impact ratings (IIC / $L'_{n,w}$), perimeter flanking strips, and waste margins directly from architectural finish schedules and floor boundary polygons.

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
class AcousticUnderlaymentType(str, Enum):
    RECYCLED_RUBBER_CRUMB = "RECYCLED_RUBBER_CRUMB"
    CROSSLINKED_PE_FOAM = "CROSSLINKED_PE_FOAM"
    CORK_ELASTOMER_COMPOSITE = "CORK_ELASTOMER_COMPOSITE"
    RESILIENT_CRADLE_BATTEN = "RESILIENT_CRADLE_BATTEN"
    UNCOUPLING_ACOUSTIC_MAT = "UNCOUPLING_ACOUSTIC_MAT"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Robust regex extraction for material type, thickness ($t_{mm}$), acoustic rating (IIC / $L'_{n,w}$ dB), and flanking strip dimensions.
2. **Polygon Area & Perimeter:** Gauss's shoelace formula for net room area ($m^2$) and boundary perimeter ($m$).
3. **Flanking Strip Takeoff:** Perimeter wall junction length ($m$) ensuring full acoustic perimeter isolation.
4. **Gross Takeoff with Standard Waste Allowance:** $A_{gross} = A_{net} \times (1 + \text{waste\_ratio})$.

## 5. Verification Plan
- Unit test suite: `tests/test_source_acoustic_underlayment_membrane_shadow.py` testing callout regex, snapping, area and perimeter calculations, flanking strip length, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
