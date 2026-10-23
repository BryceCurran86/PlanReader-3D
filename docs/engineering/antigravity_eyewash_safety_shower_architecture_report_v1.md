# Architecture Report v1: Source Emergency Eyewash & Safety Shower Station Shadow Authority

## 1. Problem Statement & Scope
Industrial facilities, laboratories, and commercial workshops require ANSI Z358.1 / AS 4775 compliant emergency eyewash and deluge safety shower stations. In architectural and hydraulic drawings, these safety stations are often confused with standard plumbing fixtures, hose bibbs, or domestic showers, losing critical regulatory parameters such as tepid water thermostatic mixing valve (TMV) setpoints (20-25°C), minimum deluge flow rates (76 L/min for showers, 11.4 L/min for eye/face washes), audio-visual alarm beacons, and flow activation switches.

This module introduces `SourceEyewashSafetyShowerShadowAuthority` to extract and validate combination safety shower and eyewash stations, bowl materials (stainless steel, ABS plastic), supply pipe diameters (DN25 - DN40), flow switch telemetry interlocks, and tepid water tempering valve requirements strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Geometric Snapping**:
   - Snapped with `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
4. **Zero Gold Dependencies**:
   - Pure deterministic regex and keyword parsing without benchmark gold dependencies.
5. **Customer Baseline Invariance**:
   - Maintains strict isolation from customer gold baselines.

## 3. Authority Interface
- `EyewashSafetyShowerCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `station_type`: `COMBINATION_SHOWER_AND_EYEWASH`, `PEDESTAL_EYEWASH_STATION`, `WALL_MOUNTED_EYEWASH`, `OVERHEAD_DRENCH_SHOWER`
  - `supply_pipe_dn`: Nominal size (e.g. `DN25`, `DN32`, `DN40`)
  - `bowl_material`: `STAINLESS_STEEL_316`, `HIGH_VISIBILITY_ABS_PLASTIC`
  - `drench_shower_flow_lpm`: Shower flow rate (litres/min)
  - `eyewash_flow_lpm`: Eyewash flow rate (litres/min)
  - `tepid_water_tmv_included`: Boolean flag indicating tepid water tempering valve
  - `flow_switch_alarm`: `FLOW_SWITCH_WITH_BEACON_ALARM`, `NONE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_eyewash_safety_shower_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceEyewashSafetyShowerShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
