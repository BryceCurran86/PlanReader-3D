# Architecture Report v1: Source Domestic Hot Water Recirculation Balancing Valve & Temperature Port Shadow Authority

## 1. Problem Statement & Scope
Domestic hot water (DHW) recirculation loops require dedicated thermostatic or dynamic balancing valves with test ports (P/T plugs or immersion wells) to maintain continuous circulation above legionella proliferation thresholds (>= 60°C in generation/ring mains, >= 55°C at branch returns) and prevent hydraulic dead-legs. In legacy extractions, DHW balancing valves were often conflated with generic isolation ball valves or gate valves, omitting critical set temperatures, thermal disinfection bypass modes, and test port provisions.

This module introduces `SourceDhwBalancingValveTempPortShadowAuthority` to extract and validate DHW recirculation balancing valves, thermostatic vs manual cartridge mechanisms, setpoint temperatures, design flow rates (L/min), test ports, and thermal disinfection capabilities strictly in shadow candidate mode.

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
- `DhwBalancingValveTempPortCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `pipe_diameter_dn`: Nominal size (e.g. `DN15`, `DN20`, `DN25`, `DN32`)
  - `valve_type`: `THERMAL_BALANCING_VALVE`, `MANUAL_CIRCUIT_SETTER_ORIFICE`, `DYNAMIC_PRESSURE_INDEPENDENT`, etc.
  - `design_flow_lpm`: Litres per minute (L/min) return flow rate
  - `set_temperature_deg_c`: Temperature setpoint in °C (e.g. 55.0, 60.0)
  - `temperature_port_type`: `PT_PRESSURE_TEMPERATURE_PLUG`, `DIRECT_IMMERSION_WELL`, `DIAL_THERMOMETER_GAUGE`, etc.
  - `disinfection_override`: `AUTOMATIC_LEGIONELLA_DISINFECTION_BYPASS`, `MANUAL_PURGE_OVERRIDE`, `NONE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_dhw_balancing_valve_temp_port_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceDhwBalancingValveTempPortShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
