# Architecture Report v1: Source Chilled Water Balancing & Modulating Control Valve Shadow Authority

## 1. Problem Statement & Scope
Chilled Water (CHW) distribution systems utilize dynamic pressure-independent control valves (PICVs) and 2-way / 3-way modulating control valves with electric actuators to regulate thermal output across air handling units (AHUs), fan coil units (FCUs), and chilled beams. In structural and MEP plan extractions, these valves are often misclassified as simple pipe couplings, generic manual valves, or omitted entirely.

This module introduces `SourceChwBalancingControlValveShadowAuthority` to extract and validate CHW modulating control valves, pressure-independent balancing assemblies (PICVs), design flow rates (L/s or L/min), differential pressure thresholds (kPa), actuator control signals (0-10V, 4-20mA, BACnet MS/TP), and fail-safe spring return positions strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Coordinate Snapping**:
   - Snapped to discrete grid using `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000` to prevent unbounded memory growth.
4. **Zero Gold Dependencies**:
   - No hardcoded benchmark sheet coordinates; pure deterministic regex and keyword parsing.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `ChwBalancingControlValveCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `pipe_diameter_dn`: Nominal size (e.g. `DN20`, `DN25`, `DN50`, `DN100`)
  - `valve_type`: `PRESSURE_INDEPENDENT_CONTROL_VALVE_PICV`, `TWO_WAY_MODULATING`, `THREE_WAY_MIXING`, etc.
  - `design_flow_lps`: Design flow rate in litres per second (L/s)
  - `differential_pressure_kpa`: Rated differential pressure requirement in kPa
  - `actuator_signal`: `0_10V_ANALOG`, `4_20MA_CURRENT_LOOP`, `BACNET_MODBUS_DIGITAL`, `FLOATING_3_POINT`
  - `fail_safe_position`: `SPRING_RETURN_NORMALLY_CLOSED`, `SPRING_RETURN_NORMALLY_OPEN`, `FAIL_IN_PLACE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_chw_balancing_control_valve_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceChwBalancingControlValveShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
