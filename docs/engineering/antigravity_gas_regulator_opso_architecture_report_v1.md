# Architecture Report v1: Source Natural Gas / LPG Service Regulator & OPSO Valve Shadow Authority

## 1. Problem Statement & Scope
Natural gas and LPG fuel gas distribution infrastructure requires service pressure regulators with integrated or downstream Over-Pressure Slam-Shut (OPSO) and Under-Pressure Shut-Off (UPSO) safety shutoff valves compliant with AS/NZS 5601.1 / NFPA 54 to prevent over-pressurization of downstream appliances and consumer piping manifolds. In hydraulic/services gas schematic drawings, gas regulators and OPSO valves are often conflated with generic isolation ball valves or omitted entirely.

This module introduces `SourceGasRegulatorOpsoShadowAuthority` to extract and validate gas regulators, gas types (Natural Gas / LPG), inlet pressures (kPa), outlet delivery pressures (1.1 kPa - 7.0 kPa / mbar), nominal pipe connections (DN20 - DN80), gas meter flow capacity (m3/h or G-rating), and external atmospheric relief vent diameters strictly in shadow candidate mode.

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
- `GasRegulatorOpsoCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `gas_service_type`: `NATURAL_GAS_NG`, `LIQUEFIED_PETROLEUM_GAS_LPG`
  - `regulator_type`: `SERVICE_REGULATOR_WITH_INTEGRAL_OPSO`, `APPLIANCE_PRESSURE_REGULATOR`, `FIRST_STAGE_LPG_HIGH_PRESSURE`
  - `pipe_connection_dn`: Nominal pipe size (e.g. `DN25`, `DN32`, `DN50`)
  - `inlet_pressure_kpa`: Maximum inlet pressure in kPa
  - `outlet_pressure_kpa`: Regulated outlet delivery pressure in kPa
  - `opso_trip_kpa`: Overpressure slam-shut cutoff trip pressure in kPa
  - `relief_vent_dn`: Atmospheric vent line diameter (e.g. `DN15`, `DN20`)
  - `position`: Snapped `(x, y)` coordinate
- `parse_gas_regulator_opso_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceGasRegulatorOpsoShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
