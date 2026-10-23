# Architecture Report v1: Source Hot Water Expansion Vessel & Relief Valve Shadow Authority

## 1. Problem Statement & Scope
Domestic and commercial pressurized hot water systems mandate potable water expansion vessels (diaphragm / bladder tanks) and combined pressure-temperature relief valves (PTRVs / safety relief valves) to absorb thermal volumetric expansion and protect calorifiers, boilers, and heat pumps from catastrophic over-pressurization. In hydraulic plumbing schematic diagrams and plantroom drawings, expansion vessels and PTRVs are often omitted or conflated with standard cold water storage tanks.

This module introduces `SourceExpansionVesselReliefValveShadowAuthority` to extract and validate hot water expansion vessels, vessel capacities (litres), factory pre-charge pressures (kPa), relief valve setpoint pressures (700 - 1400 kPa), temperature trip ratings (99°C), and copper relief discharge line diameters (DN20 - DN40) strictly in shadow candidate mode.

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
   - Pure regex and keyword parsing without benchmark gold dependencies.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `ExpansionVesselReliefValveCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `vessel_capacity_litres`: Expansion tank nominal volume in litres (L)
  - `precharge_pressure_kpa`: Vessel nitrogen pre-charge pressure (kPa)
  - `relief_valve_set_kpa`: PTRV pressure relief threshold (kPa)
  - `relief_temperature_deg_c`: Temperature relief limit (e.g. 99.0°C)
  - `relief_drain_dn`: Nominal drain/tundish pipe size (e.g. `DN20`, `DN25`, `DN32`)
  - `bladder_material`: `BUTYL_RUBBER_FOOD_GRADE`, `EPDM_MEMBRANE`, `DIAPHRAGM_POTABLE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_expansion_vessel_relief_valve_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceExpansionVesselReliefValveShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
