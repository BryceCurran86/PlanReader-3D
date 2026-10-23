# Architecture Report: Source Geotechnical Screw Pier & Helical Anchor Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Geotechnical and structural deep foundations (AS 2159 / IBC Chapter 18 / FHWA Helical Pile Design).
- **Subsystem**: Helical screw piles, screw piers, underpinning tiebacks, and helical ground anchors.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_screw_pier_helical_anchor_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `SCREW PIER`, `HELICAL PILE`, `SCREW PILE`, `HELICAL ANCHOR`, `GROUND SCREW`, `CHANCE PILE`, `TORQUE PIER`.
- **Shaft Type**:
  - `PIPE_SHAFT_CHS` (e.g. 76mm, 89mm, 114mm circular hollow section)
  - `SOLID_SQUARE_SHAFT` (e.g. 38mm, 44mm, 50mm square solid bar)
- **Extracted Attributes**:
  - `shaft_diameter_mm`: e.g. 76mm, 89mm, 114mm
  - `helix_configuration`: SINGLE_HELIX, DOUBLE_HELIX, TRIPLE_HELIX
  - `helix_diameters_mm`: e.g. [250], [250, 300], [250, 300, 350]
  - `working_capacity_kn`: e.g. 150 kN, 250 kN, 350 kN
  - `minimum_depth_m`: e.g. 4.5m, 6.0m, 8.0m
  - `target_torque_knm`: e.g. 10 kNm, 15 kNm, 20 kNm

## 3. Geometric Model
- Screw pier centroid coordinates `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_shp_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering shaft types, helix blade configurations, capacities, installation torques, coordinate snapping, dictionary serialization, and customer retention verification.
