# Architecture Report: Source High-Pressure Misting Fire Suppression Nozzle & Zoned Solenoid Valve Shadow Authority (Item 221 / Blocker 161)

## 1. Executive Summary
High-pressure water mist (HPWM) fire protection systems (e.g. Marioff HI-FOG, Danfoss Sem-Safe, Fike Micromist) operate at elevated pressures (80 bar to 140 bar), producing micro-droplets (<100 microns) that displace oxygen and absorb heat with minimal water damage. Specialized fire engineering plans detail high-pressure mist nozzles (automatic closed bulb or open deluge), micro-orifice K-factors, 316L seamless stainless steel tubing, fast-acting high-pressure solenoid control valves, and protected hazard rooms (generator enclosures, data centers, heritage archives).

This shadow authority extracts and validates high-pressure water mist nozzle and zone valve callouts and coordinates strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Special hazards fire protection drawings, data center fire engineering plans, generator enclosure suppression schematics, and water mist nozzle layout schedules.
- **First Failing Authority:** Standard wet fire sprinkler parsers treat high-pressure water mist nozzles as conventional low-pressure sprinkler heads (K80 / K115), discarding 100+ bar pressure ratings, seamless stainless steel tubing specifications, ultra-fine droplet ratings (<100 microns), and dedicated high-pressure solenoid zone valves.

## 3. Data Model & Extraction Capabilities
- `HighPressureWaterMistNozzleCallout`:
  - `raw_text`: Original unedited callout string.
  - `nozzle_type`: `HIGH_PRESSURE_WATER_MIST_NOZZLE`, `AUTOMATIC_BULB_MIST_HEAD`, `OPEN_DELUGE_MIST_NOZZLE`, `TOTAL_FLOODING_MICRO_ORIFICE`, `GENERIC_WATER_MIST_HEAD`.
  - `operating_pressure_bar`: Operating working pressure in bar (e.g., 80 bar, 100 bar, 120 bar, 140 bar).
  - `k_factor`: Flow coefficient (e.g., `K0.5`, `K1.2`, `K2.5`, `K3.6`).
  - `droplet_size_microns`: Dv90 atomized droplet size in microns (e.g., 50 microns, 80 microns, 100 microns).
  - `piping_material`: `STAINLESS_STEEL_316L`, `DUPLEX_2205`, `SEAMLESS_SS_TUBING`, `UNSPECIFIED`.
  - `zone_solenoid_valve_dn`: Zoned high-pressure solenoid valve nominal diameter (e.g., `DN15`, `DN20`, `DN25`, `DN32`).
  - `protected_hazard`: `SERVER_ROOM_DATA_CENTER`, `TURBINE_GENERATOR_ENCLOSURE`, `COMMERCIAL_KITCHEN_HOOD`, `HERITAGE_ARCHIVE_STORAGE`, `GENERAL_EQUIPMENT_ZONE`.
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
