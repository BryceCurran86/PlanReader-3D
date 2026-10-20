# Architecture Report v1: Source Stormwater Retention Sump Submersible Grinder Pump Station Shadow Authority

## 1. Problem Statement & Scope
Stormwater retention pits, detention basins, and basement drainage collection sumps rely on submersible grinder and vortex pumping stations with dual guide rail auto-coupling duckfoot discharge connections to discharge water to council stormwater mains. In previous drawing extractions, submersible pump schedules and pit detail callouts were often collapsed into generic pit dimensions, omitting pump hydraulics (e.g. duty/standby duplex configuration, flow in L/s, head in meters, and cutter/impeller mechanism), creating significant blind spots in mechanical/hydraulic coordination.

This module introduces `SourceSubmersibleGrinderPumpShadowAuthority` to extract and validate submersible pump station callouts, duty/standby duplex configurations, cutter impeller types, hydraulic performance parameters (L/s flow, head in m, motor kW), and duckfoot guide rail discharge assemblies strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Geometric Snapping**:
   - 2D coordinates snapped using `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Extraction inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000` to prevent memory exhaustion.
4. **Zero Gold Dependencies**:
   - No hardcoded project or sheet heuristics; pure deterministic regex and keyword parsing.
5. **Customer Baseline Invariance**:
   - Preserves SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 3. Authority Interface
- `SubmersibleGrinderPumpCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `pump_configuration`: `DUPLEX_DUTY_STANDBY`, `SIMPLEX_PUMP`, `TRIPLEX_SYSTEM`
  - `impeller_type`: `RADIAL_CUTTER_GRINDER`, `VORTEX_IMPELLER`, `SHREDDER_PUMP`, `SEMI_OPEN_NON_CLOG`
  - `flow_lps`: Design flow rate in litres per second (L/s)
  - `head_m`: Total dynamic head in meters (m)
  - `motor_power_kw`: Motor rated output power in kW
  - `guide_rail_coupling`: `DUAL_GUIDE_RAIL_COUPLING`, `FREE_STANDING`, `HOSE_DISCHARGE`
  - `sump_dimensions_mm`: Tuple of `(diameter_or_width, depth)` in mm
  - `position`: Snapped `(x, y)` coordinate
- `parse_submersible_grinder_pump_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceSubmersibleGrinderPumpShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
