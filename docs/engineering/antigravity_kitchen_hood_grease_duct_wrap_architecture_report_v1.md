# Architecture Report: Source Commercial Kitchen Exhaust Hood Grease Duct Fire Wrap Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Mechanical HVAC, kitchen ventilation (AS 1668.1 / NFPA 96), and fire safety engineering.
- **Subsystem**: Kitchen exhaust hood grease duct enclosure, fire wrap blanket insulation, welded grease ductwork, and cleanout access doors.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_kitchen_hood_grease_duct_wrap_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `GREASE DUCT`, `KITCHEN EXHAUST DUCT`, `KITCHEN HOOD DUCT`, `GREASE EXHAUST`, `FIRE WRAP DUCT`, `DUCT FIRE BLANKET`, `FIREMASTER WRAP`.
- **Duct Material & Construction**:
  - `WELDED_STAINLESS_STEEL` (e.g. 1.2mm grade 304/316 continuously welded)
  - `WELDED_MILD_STEEL` (e.g. 1.6mm black steel continuously welded)
- **Fire Wrap Blanket Material**:
  - `CERAMIC_FIBER_BLANKET` (e.g. Thermal Ceramics FireMaster, Pyroscat)
  - `CALCIUM_SILICATE_BOARD`
  - `BIO_SOLUBLE_WOOL`
- **Extracted Attributes**:
  - `fire_rating_hours`: 1.0, 2.0 (standard), 3.0, 4.0 hours (FRL -/120/120)
  - `wrap_thickness_mm`: e.g. 38mm, 50mm, 76mm (2x 38mm layers)
  - `duct_dimensions_mm`: e.g. "600x450", "500 DIA"
  - `cleanout_door_specified`: True/False (grease tight gasketed access panel)
  - `slope_to_hood_pct`: e.g. 2.0% (1:50)

## 3. Geometric Model
- Linear centerline polylines snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_gdw_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering duct materials, fire ratings, wrap thickness, cleanout doors, slope parsing, polyline snapping, dictionary serialization, and baseline customer retention.
