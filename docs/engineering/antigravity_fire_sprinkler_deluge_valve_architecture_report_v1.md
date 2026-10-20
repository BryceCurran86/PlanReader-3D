# Architecture Report: Source Fire Sprinkler Pre-Action Deluge Valve Station Shadow Authority (v1)

## Executive Summary
Specialised commercial and industrial facilities (such as computer server rooms, telecommunication centers, refrigerated freezers, and aircraft hangars) require specialized water-based fire suppression mechanisms that prevent premature or accidental water discharge. Pre-action systems maintain supervisory air pressure in distribution pipework and require electric solenoid actuation, pneumatic pilot depressurization, or both (double-interlock) before admitting water into the system. Deluge systems utilize open nozzles fed simultaneously upon deluge valve tripping.
This report defines the candidate shadow authority for parsing and extracting pre-action and deluge sprinkler valve station coordinates, trim configurations, and release modes from fire services drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `PRE-ACTION VALVE`, `DELUGE VALVE`, `PREACTION VALVE`, `DELUGE VALVE STATION`, `DOUBLE INTERLOCK PRE-ACTION`, `SINGLE INTERLOCK`, `SPRINKLER CONTROL VALVE STATION`.
2. **Key Physical Parameters**:
   - `valve_type`: `DOUBLE_INTERLOCK_PREACTION`, `SINGLE_INTERLOCK_PREACTION`, `DELUGE_VALVE`, `NON_INTERLOCK_PREACTION`.
   - `diameter_dn_mm`: Valve size (e.g. `DN80`, `DN100`, `DN150`, `DN200`).
   - `release_type`: `ELECTRIC_SOLENOID`, `PNEUMATIC_PILOT`, `HYDRAULIC_RELEASE`, `MANUAL_EMERGENCY`.
   - `rated_pressure_kpa`: Rated working pressure (e.g. `1200 kPa`, `1600 kPa`).
   - `has_accelerator`: Quick-opening device for pneumatic trim.
3. **Geometric Snapping & Polyline Representation**:
   - Valve station points and trim headers snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or coordinate length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
