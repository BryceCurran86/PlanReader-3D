# Architecture Report: Source Swimming Pool Overflow Scupper & Perimeter Balance Tank Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Aquatic center engineering, commercial pool hydraulics (AS 3979 / SPASA / FINA standards).
- **Subsystem**: Wet deck perimeter overflow gutter scuppers, grating systems, balance tank retention chambers, and recirculation gravity drain lines.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_pool_scupper_balance_tank_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `POOL OVERFLOW`, `WET DECK GUTTER`, `BALANCE TANK`, `SCUPPER OUTLET`, `PERIMETER SCUPPER`, `SURGE TANK`, `POOL GUTTER GRATING`.
- **Gutter Grating Material**:
  - `POLYPROPYLENE_TRANSVERSE` (anti-slip PP modular grating)
  - `STAINLESS_STEEL_WEDGE_WIRE` (marine grade 316)
  - `FINGER_SAFE_SLOT_DRAIN` (concealed architectural slot)
- **Extracted Attributes**:
  - `gutter_width_mm`: e.g. 200mm, 250mm, 300mm
  - `gutter_depth_mm`: e.g. 150mm, 200mm, 250mm
  - `balance_tank_capacity_litres`: e.g. 15000L, 20000L, 25000L (or m³ converted to L)
  - `drain_pipe_dia_mm`: e.g. 150mm, 200mm, 250mm PVC-U
  - `level_sensors_present`: True/False (float switch or ultrasonic)

## 3. Geometric Model
- Scupper gutter perimeter polyline or balance tank node point snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_pbt_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering grating materials, gutter dimensions, balance tank volume conversions, drainage diameters, polyline snapping, dictionary serialization, and customer retention verification.
