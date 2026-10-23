# Architecture Report v1: Source Fire Smoke Damper Fusible Link & Microswitch Actuator Shadow Authority

## 1. Problem Statement & Scope
Heating, ventilation, and air-conditioning (HVAC) duct penetrations passing through fire-resistant compartment walls, plant room boundaries, and vertical service risers require certified motorized fire/smoke dampers (FSD) or fusible link fire dampers (FD). Crucially, smoke management systems (AS/NZS 1668.1) demand spring-return motorized actuators with auxiliary microswitches (reporting both open and closed positions back to fire indicator panels) and thermal triggers (typically 71°C or 74°C fusible links). Legacy extractions frequently collapsed fire dampers into generic duct fittings, dropping actuator control voltages, thermal link ratings, and microswitch signaling attributes.

This module introduces `SourceFireSmokeDamperMicroswitchShadowAuthority` to extract and validate fire and smoke damper callouts, actuator mechanisms (motorized 24V/240V spring return vs thermal fusible link gravity), auxiliary microswitches, thermal release ratings (°C), duct dimensions, and FRL ratings strictly in shadow candidate mode.

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
- `FireSmokeDamperMicroswitchCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `damper_type`: `COMBINATION_FIRE_SMOKE_DAMPER`, `INTUMESCENT_FIRE_DAMPER`, `CURTAIN_FIRE_DAMPER`, `SMOKE_CONTROL_DAMPER`
  - `actuator_control`: `MOTORISED_SPRING_RETURN_24V`, `MOTORISED_SPRING_RETURN_240V`, `THERMAL_FUSIBLE_LINK_GRAVITY`, etc.
  - `fusible_link_rating_deg_c`: Thermal release temperature in °C (e.g. 71.0, 74.0, 93.0)
  - `auxiliary_microswitch`: `OPEN_AND_CLOSED_MICROSWITCHES`, `CLOSED_ONLY_MICROSWITCH`, `NONE`
  - `duct_dimensions_mm`: Tuple of `(width, height)` in mm
  - `frl_minutes`: Fire-resistance level in minutes (e.g. 120, 240, 60)
  - `position`: Snapped `(x, y)` coordinate
- `parse_fire_smoke_damper_microswitch_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceFireSmokeDamperMicroswitchShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
