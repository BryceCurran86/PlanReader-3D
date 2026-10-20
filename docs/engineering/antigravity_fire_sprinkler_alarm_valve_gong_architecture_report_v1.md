# Architecture Report: Source Fire Sprinkler Alarm Check Valve & Water Motor Gong Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Fire protection engineering, automatic fire sprinkler systems (AS 2118.1 / NFPA 13).
- **Subsystem**: Wet pipe alarm check valves, retard chambers, water motor alarm gongs, test/drain valves, and supervisory pressure switches.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_fire_sprinkler_alarm_valve_gong_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `ALARM CHECK VALVE`, `WET ALARM VALVE`, `WATER MOTOR GONG`, `SPRINKLER ALARM VALVE`, `RETARD CHAMBER`, `SPRINKLER CONTROL VALVE`, `MOTOR GONG`.
- **Valve Station Configuration**:
  - `VARIABLE_PRESSURE_RETARD` (wet system with retard chamber for municipal water fluctuations)
  - `CONSTANT_PRESSURE` (wet system with direct alarm connection, e.g. dedicated fire tank supply)
- **Extracted Attributes**:
  - `valve_size_mm`: e.g. 100mm, 150mm, 200mm (DN100, DN150, DN200)
  - `water_motor_gong_present`: True/False (external hydraulic bell)
  - `retard_chamber_present`: True/False
  - `pressure_switch_present`: True/False (alarm trip to FIP)
  - `main_drain_size_mm`: e.g. 50mm (DN50)
  - `working_pressure_kpa`: e.g. 1200 kPa, 1400 kPa, 175 psi

## 3. Geometric Model
- Sprinkler valve station point coordinates `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_avg_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering valve sizes, retard chambers, motor gong detection, pressure switch presence, drain valve sizing, coordinate snapping, dictionary serialization, and customer retention verification.
