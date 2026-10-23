# Architecture Report v1: Source Cold Water RPZ Backflow Prevention Device Strainer Shadow Authority

## 1. Problem Statement & Scope
Potable water supply branch connections to high-hazard contamination fixtures (commercial kitchens, chemical dosing plants, cooling towers, irrigation systems, and laboratories) mandate certified Reduced Pressure Zone Device (RPZD / RPZ) backflow preventers with upstream Y-strainers and air gap tundish drainage according to AS/NZS 3500.1 / IPC / UPC plumbing codes. In previous extractions, RPZ assemblies were frequently conflated with standard dual check or isolation valves, omitting critical upstream strainer protection, high-hazard classification, lockable ball/gate valves, and air-gap tundish discharge details.

This module introduces `SourceRpzBackflowStrainerShadowAuthority` to extract and validate RPZ backflow prevention callouts, upstream Y-strainer configurations, high/medium hazard classifications, nominal DN sizes, isolation valves, and tundish drain air-gap provisions strictly in shadow candidate mode.

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
- `RpzBackflowStrainerCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `device_type`: `REDUCED_PRESSURE_ZONE_RPZ`, `DOUBLE_CHECK_VALVE_DCV`, `DUAL_CHECK_VALVE`, `VACUUM_BREAKER`
  - `hazard_rating`: `HIGH_HAZARD`, `MEDIUM_HAZARD`, `LOW_HAZARD`
  - `nominal_size_dn`: Nominal size designation (e.g. `DN25`, `DN32`, `DN50`, `DN80`)
  - `strainer_type`: `Y_TYPE_STRAINER_BLOWDOWN`, `BASKET_STRAINER`, `INTEGRAL_STRAINER`, `NONE`
  - `isolation_valves`: `FULL_BORE_BALL_VALVES_LOCKABLE`, `RESILIENT_SEAT_GATE_VALVES_OSY`, `BUTTERFLY_VALVES_GEAR_OPERATED`
  - `relief_drain_air_gap_tundish`: `TUNDISH_AIR_GAP_DRAIN`, `DIRECT_DRAIN_RUNOUT`, `UNSPECIFIED`
  - `position`: Snapped `(x, y)` coordinate
- `parse_rpz_backflow_strainer_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceRpzBackflowStrainerShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
