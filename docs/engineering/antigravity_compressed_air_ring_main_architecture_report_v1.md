# Architecture Report: Source Compressed Air Ring Main Aluminum Piping Drop Leg & Filter Regulator Shadow Authority (Item 223 / Blocker 163)

## 1. Executive Summary
Modern industrial workshops, production manufacturing plants, and maintenance sheds employ modular extruded aluminum piping systems (e.g. Transair, AIRnet, Prevost) configured as closed-loop overhead ring mains to deliver constant pneumatic pressure with minimal pressure drop. Engineered drop legs branch off the top of the horizontal header via swan-neck takeoffs (preventing condensed water ingress) down to workstation level, terminating in Filter-Regulator-Lubricator (FRL) combination units, safety venting quick-disconnect couplers, and automated condensate drains.

This shadow authority extracts and validates compressed air ring main, aluminum pipe diameter, drop leg, and FRL workstation callouts and geometries strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Mechanical pneumatic piping plans, workshop equipment layout details, compressed air schematics, and mechanical services riser schedules.
- **First Failing Authority:** Downstream plumbing and mechanical parsers treat aluminum air lines as generic domestic cold water or hydraulic pipework, dropping overhead loop topology, swan-neck moisture takeoffs, operating pressures (7 to 16 bar), and workstation FRL units.

## 3. Data Model & Extraction Capabilities
- `CompressedAirRingMainCallout`:
  - `raw_text`: Original unedited callout string.
  - `piping_system_type`: `ALUMINUM_COMPRESSED_AIR_RING_MAIN`, `SWAN_NECK_DROP_LEG`, `FRL_UNIT_WORKSTATION`, `COMPRESSED_AIR_HEADER`, `GENERIC_PNEUMATIC_PIPE`.
  - `pipe_diameter_mm`: Outer diameter of modular aluminum pipe (e.g. 20mm, 25mm, 40mm, 50mm, 63mm, 80mm).
  - `operating_pressure_bar`: Working pneumatic pressure in bar (e.g., 7 bar, 8 bar, 10 bar, 12 bar, 16 bar).
  - `point_of_use_frl`: `FILTER_REGULATOR_LUBRICATOR_COMBO`, `FILTER_REGULATOR_ONLY`, `COALESCING_OIL_REMOVAL_FILTER`, `UNSPECIFIED`.
  - `condensate_drain`: `AUTOMATIC_FLOAT_DRAIN`, `ZERO_LOSS_ELECTRONIC_DRAIN`, `MANUAL_DRAIN_VALVE`, `UNSPECIFIED`.
  - `quick_coupling_safety`: `VENTING_SAFETY_QUICK_COUPLING`, `EURO_HIGH_FLOW_COUPLING`, `NITTO_STYLE_PLUG`, `UNSPECIFIED`.
  - `service_designation`: `PLANT_COMPRESSED_AIR`, `INSTRUMENT_AIR`, `BREATHING_AIR`, `WORKSHOP_PNEUMATIC_TOOL`.
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
