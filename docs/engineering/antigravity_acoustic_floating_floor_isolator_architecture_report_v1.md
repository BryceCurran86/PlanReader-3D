# Architecture Report: Source Acoustic Floating Floor Isolator Jack-Up Mount Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Acoustic engineering, building acoustics (ISO 10140 / AS/NZS ISO 717.2), vibration isolation.
- **Subsystem**: Acoustic floating floors, jack-up spring boxes/canisters, elastomeric isolation pads, perimeter flanking isolation boards, and cavity air gaps.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_acoustic_floating_floor_isolator_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `FLOATING FLOOR`, `ACOUSTIC FLOATING SLAB`, `JACK-UP ISOLATOR`, `JACK UP MOUNT`, `SPRING ISOLATOR CANISTER`, `NEOPRENE FLOOR MOUNT`, `PERIMETER ISOLATION BOARD`.
- **Isolator Types**:
  - `JACK_UP_SPRING_CANISTER` (e.g. Mason FSN / Kinetics encased helical steel spring)
  - `ELASTOMERIC_NEOPRENE_PAD` (e.g. high-density ribbed neoprene / natural rubber mount)
  - `POLYURETHANE_FOAM_MAT` (e.g. continuous Sylomer / Regupol acoustic underlay)
- **Extracted Attributes**:
  - `floating_slab_thickness_mm`: e.g. 100mm, 150mm, 200mm reinforced concrete slab
  - `air_cavity_height_mm`: e.g. 50mm, 75mm, 100mm air gap
  - `perimeter_isolation_thickness_mm`: e.g. 15mm, 20mm flanking board
  - `grid_spacing_mm`: e.g. 1000mm, 1200mm, 1500mm spacing
  - `natural_frequency_hz`: e.g. 3.5 Hz, 5.0 Hz, 8.0 Hz

## 3. Geometric Model
- Isolator point coordinates `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_aff_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering isolator types, slab thickness, air gap parsing, natural frequency detection, grid coordinates, dictionary serialization, and customer retention verification.
