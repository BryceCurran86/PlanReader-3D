# Architecture Report v1: Source Elevator Shaft Smoke Relief Vent & Motorized Louver Shadow Authority

## 1. Problem Statement & Scope
Building codes (e.g. NCC / IBC Section 3004) mandate smoke pressure relief ventilation at the top of enclosed elevator hoistways and lift shafts to prevent smoke logging of escape stairs and adjacent elevator lobbies during a building fire. Smoke relief vents require motorized weatherproof architectural louvers with 24V DC fail-safe spring-return actuators, aerodynamic free area requirements (typically minimum 0.1 m2 or 3.5% of hoistway cross-sectional area), bird/insect screens, and fire alarm panel interface relays. In architectural roof plans and mechanical ventilation sections, hoistway smoke vents are often mistaken for standard plantroom louvers or roof cowls.

This module introduces `SourceElevatorSmokeReliefVentShadowAuthority` to extract and validate elevator hoistway smoke vents, motorized relief louvers, aerodynamic free area (m2), overall dimensions (width x height mm), actuator voltage & fail-safe operation, and weather louver blade profiles strictly in shadow candidate mode.

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
- `ElevatorSmokeReliefVentCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `vent_type`: `MOTORIZED_HOISTWAY_SMOKE_RELIEF_LOUVER`, `GRAVITY_COUNTERBALANCED_PRESSURE_RELIEF_VENT`, `ROOF_UPSTAND_VENT_COWL`
  - `width_mm`: Overall louver width (mm)
  - `height_mm`: Overall louver height (mm)
  - `aerodynamic_free_area_m2`: Net aerodynamic free vent area (m2)
  - `actuator_operation`: `FAIL_SAFE_SPRING_OPEN_24V_DC`, `PNEUMATIC_FAIL_OPEN`, `MANUAL_FUSIBLE_LINK`
  - `blade_profile`: `DRAINABLE_WEATHER_BLADE`, `CHEVRON_ACOUSTIC_BLADE`, `STANDARD_ARCHITECTURAL_BLADE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_elevator_smoke_relief_vent_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceElevatorSmokeReliefVentShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
