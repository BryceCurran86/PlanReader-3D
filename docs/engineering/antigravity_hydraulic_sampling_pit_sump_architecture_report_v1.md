# Architecture Report: Source Hydraulic Grease Waste Sampling Pit & Sump Pump Shadow Authority (v1)

## Executive Summary
Commercial kitchen, hospital, laboratory, and shopping centre developments discharge trade wastewater into the authority sewer network subject to strict water quality monitoring. Local water authorities require precast concrete trade waste sampling pits downstream of grease traps or neutralizers with standard tumbling invert drop or sampling spoon clearance and gas-tight sealed covers. Where basement drainage is below street sewer inverts, dedicated submersible duplex (duty/standby) sump pump pits lift effluent to higher mains.
This report establishes the candidate shadow authority for parsing and extracting trade waste sampling pits, sump pump pits, chamber dimensions, and pump configurations from hydraulic and civil engineering plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `TRADE WASTE SAMPLING PIT`, `GREASE WASTE SAMPLING PIT`, `SAMPLING PIT`, `TRADE WASTE PIT`, `SUMP PUMP`, `SUBMERSIBLE PUMP PIT`, `SEWAGE EJECTOR PIT`.
   - Negation filtering: Explicitly ignores non-sampling annotations (e.g. `NO SAMPLING PIT REQUIRED`).
2. **Key Physical Parameters**:
   - `pit_type`: `SAMPLING_PIT`, `SUMP_PUMP_PIT`, `SEWAGE_EJECTOR_PIT`, `MONITORING_WELL`.
   - `pit_dimensions_mm`: Plan size (e.g. `600x600`, `900x900`, `1200 DIA`).
   - `depth_mm`: Chamber depth (e.g. `900MM`, `1200MM`, `1800MM`).
   - `pump_configuration`: `DUPLEX_DUTY_STANDBY`, `SIMPLEX`, `TRIPLEX`, `NONE_GRAVITY_PIT`.
   - `cover_type`: `GAS_TIGHT_CLASS_B`, `HEAVY_DUTY_CLASS_D`, `PEDESTRIAN_CLASS_A`.
3. **Geometric Snapping & Polyline Representation**:
   - Pit center points and chamber outline lines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or coordinate span.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
