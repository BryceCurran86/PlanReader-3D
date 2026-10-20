# Architecture Report: Source Emergency Eyewash & Safety Shower Thermostatic Mixing Valve (TMV) Shadow Authority (Item 224 / Blocker 164)

## 1. Executive Summary
Emergency decontamination equipment (safety showers, eye/face wash fixtures, drench showers) governed by ANSI Z358.1 / AS 4775 must supply tepid water (16°C–38°C) at minimum flow rates (75–115 L/min for combination units) for 15 minutes of uninterrupted flushing. Dedicated emergency thermostatic mixing valves (emergency TMVs / ETVs) blend hot and cold supplies while incorporating essential fail-safe mechanisms: positive hot-water shutoff to prevent scalding and an internal cold-water bypass that guarantees full flow if hot supply fails. Hydraulic details also feature flow switch alarms, local strobe beacons, and floor waste drainage connections.

This shadow authority extracts and validates emergency shower/eyewash stations, tepid water mixing valves, cold water bypass capacities, and alarm actuation callouts strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Hydraulic plumbing drawings, laboratory layout plans, safety equipment schedules, industrial chemical handling layouts, and battery room details.
- **First Failing Authority:** Downstream domestic plumbing parsers classify emergency showers as standard ablution showers or generic hand basins, omitting high-capacity emergency TMVs (75–130 L/min), fail-safe cold bypass channels, strobe alarm switches, and tepid water setpoint controls.

## 3. Data Model & Extraction Capabilities
- `EmergencyShowerEyewashTmvCallout`:
  - `raw_text`: Original unedited callout string.
  - `station_type`: `COMBINATION_SHOWER_EYEWASH`, `PEDESTAL_EYEWASH_STATION`, `WALL_MOUNTED_EYE_FACE_WASH`, `OVERHEAD_DRENCH_SHOWER`, `GENERIC_SAFETY_SHOWER`.
  - `tmv_capacity_lpm`: Extracted emergency TMV flow capacity in L/min.
  - `temperature_setpoint_celsius`: Tepid water setpoint in °C (e.g., 25°C, 28°C, 30°C).
  - `cold_water_bypass`: `FAIL_SAFE_COLD_BYPASS`, `INTERNAL_COLD_WATER_BYPASS`, `POSITIVE_HOT_WATER_SHUTOFF`, `UNSPECIFIED`.
  - `alarm_actuation`: `FLOW_SWITCH_ALARM_HORN`, `STROBE_ALARM_BEACON`, `BMS_SUPERVISORY_CONTACT`, `UNSPECIFIED`.
  - `inlet_drain_dn`: Inlet supply pipe size (e.g. `DN25`, `DN32`, `DN40`).
  - `service_hazard`: `BATTERY_CHARGING_ROOM`, `CHEMICAL_DOSING_AREA`, `LABORATORY_CORRIDOR`, `WORKSHOP_DECONTAMINATION`, `GENERAL_INDUSTRIAL_HAZARD`.
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
