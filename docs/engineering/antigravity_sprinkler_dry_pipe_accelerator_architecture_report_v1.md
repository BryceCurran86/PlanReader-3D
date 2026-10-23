# Architecture Report: Source Fire Sprinkler Dry Pipe Accelerator Quick Opening Device Shadow Authority (Item 217 / Blocker 157)

## 1. Executive Summary
Dry pipe automatic fire sprinkler systems protecting areas vulnerable to freezing (unheated loading bays, subgrade parking structures, chilled cold-storage warehouses, canopies) require quick-opening devices (QOD)—specifically dry pipe accelerators or exhausters—when system volume exceeds code thresholds (typically >500 gallons / >1900 L). Accelerators sense minor differential pressure drops upon head actuation and immediately dump air into the intermediate chamber to accelerate dry valve clapper unseating within 60 seconds. Details specify accelerator models (e.g. Reliable Model B1, Viking Model E-1), dry pipe valve sizes (DN100, DN150, DN200), integral anti-flooding devices, and air/water trim pressure gauges.

This shadow authority extracts and validates dry pipe accelerator and quick-opening device callouts and coordinates strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Fire protection schematic drawings, dry pipe valve trim riser details, hydraulic sprinkler schedules, and sprinkler plant room drawings.
- **First Failing Authority:** Downstream wet/dry fire protection parsers treat the dry pipe riser as a single generic valve symbol, dropping the accelerator quick-opening device, anti-flooding isolation mechanisms, trim differential gauges, and freeze-exposure service classifications.

## 3. Data Model & Extraction Capabilities
- `SprinklerDryPipeAcceleratorCallout`:
  - `raw_text`: Original unedited callout string.
  - `device_type`: `DRY_PIPE_ACCELERATOR`, `SYSTEM_EXHAUSTER`, `QUICK_OPENING_DEVICE`, `DIFFERENTIAL_ACCELERATOR`, `GENERIC_DRY_VALVE_TRIM`.
  - `valve_connection_dn`: Extracted accelerator connection nominal diameter (e.g., `DN15`, `DN20`, `DN25`).
  - `dry_valve_size_dn`: Associated dry pipe valve nominal diameter (e.g., `DN100`, `DN150`, `DN200`).
  - `anti_flooding_device`: `INTEGRAL_ANTI_FLOODING_DEVICE`, `SEPARATE_ANTI_FLOOD_BALL_VALVE`, `AIR_RESTRICTION_ORIFICE`, `UNSPECIFIED`.
  - `trim_pressure_gauges`: `AIR_WATER_DUAL_PRESSURE_GAUGE`, `AIR_PRESSURE_GAUGE`, `SYSTEM_TRIM_GAUGE`, `UNSPECIFIED`.
  - `rated_operating_pressure_kpa`: Rated working pressure (e.g., 1200 kPa, 1400 kPa, 175 psi).
  - `service_hazard`: `FREEZING_EXPOSURE`, `REFRIGERATED_WAREHOUSE`, `CAR_PARK`, `ATTIC_PROTECTION`, `GENERIC_DRY_ZONE`.
  - `position`: Snapped `(x, y)` coordinate.
  - `status`: Constant `"CANDIDATE"`.
  - `commercial_projection_allowed`: Constant `False`.
  - `takeoff_eligible`: Constant `False`.
  - `metadata`: Supplemental dictionary.

## 4. Invariants & Safety
- Strict shadow candidate isolation: no commercial projection or takeoff eligibility.
- Global 2.5 pt coordinate snapping (`SNAP_TOLERANCE_PT = 2.5`).
- Maximum 20,000 primitive safety cap (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
- Customer retention baseline verification: byte-for-byte invariance maintained on `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
