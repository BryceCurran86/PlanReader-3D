# Architecture Report: Source Fire Door Electro-Magnetic Hold-Open Release & Door Selector Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Architectural hardware, life safety & fire protection engineering (AS 1905.1 / NFPA 80 / IBC Chapter 7).
- **Subsystem**: Fire doors, electro-magnetic door hold-open devices (24VDC fire trip release), sequential door coordinators/selectors for rebated leaf pairs, and fire ratings.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_fire_door_mag_hold_open_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `MAG HOLD OPEN`, `MAGNETIC HOLD OPEN`, `DOOR SELECTOR`, `DOOR COORDINATOR`, `ELECTRO-MAGNETIC HOLDER`, `MAGNETIC DOOR HOLDER`, `FIRE DOOR HOLD OPEN`, `REBATED DOOR SELECTOR`.
- **Door Leaf Configuration**:
  - `DOUBLE_LEAF_REBATED` (pair of doors with rebated meeting stiles requiring sequence selector)
  - `DOUBLE_LEAF_PLAIN` (pair of doors without rebate)
  - `SINGLE_LEAF` (single fire door leaf)
- **Extracted Attributes**:
  - `fire_rating_hours`: e.g. 1.0, 2.0, 3.0, 4.0 (or -/60/30, -/120/30)
  - `mount_type`: WALL_MOUNT, FLOOR_MOUNT, OVERHEAD_SURFACE
  - `voltage`: 24V_DC, 240V_AC
  - `smoke_release_interface`: True/False (automatic release on fire alarm / smoke detection)
  - `sequential_selector_required`: True/False (required for rebated double doors)

## 3. Geometric Model
- Door opening insertion point `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_mho_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering leaf configurations, fire ratings, mount types, voltage detection, smoke alarm release, point snapping, dictionary serialization, and customer retention verification.
