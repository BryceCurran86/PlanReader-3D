# Architecture Report: Source Fire Protection Deluge Valve & Open Nozzle Water Spray Shadow Authority (v1)

## 1. Executive Summary
High-hazard facility protection (such as major electrical transformers, hazardous chemical storage, aircraft hangars, and flammable liquid dispensing bays) mandates water spray deluge systems complying with AS 2118.2 and NFPA 15. In these systems, all discharge nozzles are permanently open, and water supply is arrested by an automatic quick-opening differential diaphragm or mechanical clapper deluge valve. Detection systems (infrared/UV flame detectors or pneumatic heat detectors) trigger electric solenoid or pneumatic pilot release valves to instantly flood the entire distribution manifold. Capturing deluge valves, open directional spray nozzles, K-factors, and manual emergency trip stations provides vital life-safety authority without disrupting baseline customer takeoff calculations.

## 2. Geometry & Extraction Model
- **Component Categories**:
  - `DELUGE_VALVE_SET`: Quick-opening deluge valve station with trim manifold and water motor alarm gong.
  - `OPEN_WATER_SPRAY_NOZZLE`: Open directional high-velocity or medium-velocity spray projectors.
  - `COMBINED_DELUGE_ARRAY`: Integrated deluge valve and spray manifold schedule.
- **Valve Nominal Sizes**: Standard flanged/grooved ductile iron deluge valves (DN80, DN100, DN150).
- **Actuation Trim Modes**: 24V DC solenoid valve, pneumatic pilot line, or wet hydraulic pilot loop.
- **Nozzle Projector Specs**: High/medium velocity directional nozzles with K-factors (e.g. K23, K44, K80) and spray cone patterns (e.g. 90°, 120°).
- **Emergency Release**: Manual local pull station emergency trim line.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
