# Architecture Report: Source Laboratory Fume Hood Acid Neutralization Polypropylene Tank Shadow Authority (Item 218 / Blocker 158)

## 1. Executive Summary
Laboratory plumbing plans, scientific educational buildings, and biotech cleanrooms specify specialized acid waste drainage infrastructure. Chemical effluent from fume hoods, cup sinks, and wash stations must be neutralized prior to municipal sanitary discharge. Systems range from point-of-use under-sink polypropylene limestone chip traps (5L–50L) to centralized below-ground or basement pH neutralization basins (200L–2000L) equipped with automated pH sensor controllers, chemical metering pumps, sampling ports, and high-level alarms.

This shadow authority extracts and validates laboratory acid neutralization tank and basin callouts and geometries strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Hydraulic laboratory trade waste drawings, laboratory furniture details, acid waste piping schematics, and chemical drainage schedules.
- **First Failing Authority:** Downstream drainage parsers mistake acid neutralization tanks for ordinary grease traps or generic sanitary waste sumps, omitting corrosion-resistant polypropylene/PVDF construction, limestone neutralizing media, pH instrumentation probes, and fume hood/cup sink connection topology.

## 3. Data Model & Extraction Capabilities
- `LabAcidNeutralizationTankCallout`:
  - `raw_text`: Original unedited callout string.
  - `tank_type`: `UNDER_SINK_NEUTRALIZATION_TRAP`, `CENTRAL_DILUTION_BASIN`, `LIMESTONE_CHIP_NEUTRALIZATION_TANK`, `AUTOMATIC_PH_NEUTRALIZATION_SYSTEM`, `GENERIC_ACID_WASTE_TANK`.
  - `tank_capacity_litres`: Extracted volume in litres (converted from gallons if specified).
  - `tank_material`: `POLYPROPYLENE_PP`, `HIGH_DENSITY_POLYETHYLENE_HDPE`, `PVDF`, `UNSPECIFIED`.
  - `neutralization_medium`: `CALCIUM_CARBONATE_LIMESTONE_CHIPS`, `CAUSTIC_SODA_DOSING`, `DILUTION_WATER_BAFFLE`, `UNSPECIFIED`.
  - `monitoring_instrumentation`: `PH_SENSOR_PROBE_CONTROLLER`, `HIGH_LEVEL_ALARM_SWITCH`, `SAMPLING_PORT_MANHOLE`, `UNSPECIFIED`.
  - `inlet_outlet_dn`: Extracted acid pipe size (e.g. `DN40`, `DN50`, `DN80`, `DN100`).
  - `service_environment`: `LABORATORY_FUME_HOOD`, `CUP_SINK`, `CLEANROOM_BENCH`, `GENERAL_ACID_WASTE`.
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
