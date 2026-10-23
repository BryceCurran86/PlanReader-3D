# Architecture Report: Source Condenser Water Cooling Tower Side Stream Centrifugal Separator Shadow Authority (Item 214 / Blocker 154)

## 1. Executive Summary
Commercial cooling towers and open-loop condenser water circuits continuously accumulate airborne dust, particulate matter, scaling debris, and suspended solids. Mechanical plant room drawings specify side-stream filtration systems—primarily centrifugal vortex / hydrocyclone solid-liquid separators, media sand filters, or automatic backwash strainers—often coupled with basin sweeper piping networks, dedicated booster pumps, automated motorized purge valves, and solids collection/bag recovery vessels.

This shadow authority extracts and validates condenser water side-stream separator callouts and spatial indicators strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Mechanical HVAC plant room schematics, cooling tower piping arrangement details, mechanical equipment schedules, and side-stream filtration specifications.
- **First Failing Authority:** Downstream mechanical piping and equipment parsers mistake side-stream centrifugal separator skids for standard in-line pipe fittings or generic inline strainers, dropping basin sweeper flow capacities, automatic motorized blowdown purge valves, solids collection recovery vessels, and dedicated booster pumps.

## 3. Data Model & Extraction Capabilities
- `CoolingTowerSideStreamSeparatorCallout`:
  - `raw_text`: Original unedited callout string.
  - `separator_type`: `CENTRIFUGAL_HYDROCYCLONE`, `SIDE_STREAM_SAND_FILTER`, `AUTOMATIC_BACKWASH_STRAINER`, `BASIN_SWEEPER_PACKAGE`, `GENERIC_SIDE_STREAM_SEPARATOR`.
  - `flow_rate_lps`: Liquid flow rate in L/s or converted from GPM.
  - `nominal_pipe_dn`: Extracted nominal diameter (e.g. `DN50`, `DN80`, `DN100`, `DN150`).
  - `purge_mechanism`: `AUTOMATIC_MOTORIZED_PURGE_VALVE`, `MANUAL_BLOWDOWN`, `SOLENOID_TIMED_PURGE`, `UNSPECIFIED`.
  - `solids_recovery_vessel`: `RECOVERY_BAG_VESSEL`, `SLUDGE_SETTLING_CHAMBER`, `SUMP_BLOWDOWN_DRAIN`, `UNSPECIFIED`.
  - `pump_skid_mount`: `SKID_MOUNTED_PACKAGE`, `SEPARATE_BOOSTER_PUMP`, `BASIN_SUCTION_JET`, `UNSPECIFIED`.
  - `service_designation`: `CONDENSER_WATER`, `COOLING_TOWER_BASIN`, `CLOSED_CIRCUIT_FLUID_COOLER`, `CHILLED_WATER`.
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
