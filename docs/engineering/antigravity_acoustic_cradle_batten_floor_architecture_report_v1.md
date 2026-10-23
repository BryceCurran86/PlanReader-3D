# Architecture Report: Source Acoustic Floating Timber Floor Battens & Cradle Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Architectural acoustics, impact sound insulation (ISO 10140 / Building Code of Australia Part F5 / Approved Document E).
- **Subsystem**: Acoustic cradles, floating timber battens, subfloor acoustic voids, acoustic insulation quilts, and perimeter flanking isolation bands.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_acoustic_cradle_batten_floor_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `ACOUSTIC CRADLE`, `FLOATING BATTEN`, `ACOUSTIC CRADLE FLOOR`, `SPRUNG TIMBER FLOOR`, `ACOUSTIC BATTEN`, `CRADLE AND BATTEN`, `RESILIENT CRADLE`, `TIMBER SPORTS FLOOR`.
- **Cradle Material**:
  - `RECYCLED_CRUMB_RUBBER` (e.g. high-performance vulcanised rubber crumb)
  - `ELASTOMERIC_NEOPRENE`
  - `POLYPROPYLENE_ADJUSTABLE` (e.g. screwjack pedestal with rubber foot)
- **Extracted Attributes**:
  - `batten_profile_description`: e.g. "45x45", "45x70", "50x50"
  - `batten_spacing_mm`: e.g. 400mm, 450mm, 600mm CTS
  - `cradle_void_height_mm`: e.g. 35mm, 50mm, 75mm, 100mm
  - `insulation_infill_thickness_mm`: e.g. 25mm, 50mm mineral wool / polyester batt
  - `decking_thickness_mm`: e.g. 18mm, 22mm tongue & groove timber / chipboard
  - `perimeter_flanking_band_thickness_mm`: e.g. 10mm, 15mm foam strip

## 3. Geometric Model
- Floating floor alignment polyline snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_cbf_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering cradle materials, batten profiles, spacings, void heights, insulation infill, perimeter flanking, polyline snapping, dictionary serialization, and customer retention verification.
