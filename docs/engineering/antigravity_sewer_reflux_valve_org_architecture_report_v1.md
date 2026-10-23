# Architecture Report v1: Source Sanitary Sewer Reflux Valve & Overflow Relief Gully Shadow Authority

## 1. Problem Statement & Scope
Sanitary plumbing systems require external Overflow Relief Gullies (ORGs) and sewer reflux (non-return backwater) valves compliant with AS/NZS 3500.2 / IPC Section 715 to prevent municipal sewer surcharges, flood waters, and backup inundation from entering habitable building finished floor levels. In plumbing drainage and civil plans, ORGs and reflux valves are frequently misclassified as standard stormwater floor wastes or inspection openings, omitting required spill level freeboard clearances (minimum 150mm below internal fixture spill level and 75mm above paved ground).

This module introduces `SourceSewerRefluxValveOrgShadowAuthority` to extract and validate sanitary sewer reflux valves, overflow relief gullies, nominal pipe diameters (DN100 - DN150), grate types (loose pop-up plastic / cast iron / brass), flapper check mechanisms, and required spill level elevations strictly in shadow candidate mode.

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
- `SewerRefluxValveOrgCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `fixture_type`: `OVERFLOW_RELIEF_GULLY_ORG`, `SEWER_REFLUX_BACKWATER_VALVE`, `COMBINED_ORG_WITH_REFLUX_VALVE`
  - `pipe_diameter_dn`: Nominal sewer size (e.g. `DN100`, `DN150`)
  - `grate_type`: `LOOSE_POP_UP_PLASTIC_GRATE`, `CAST_IRON_HINGED_GRATE`, `BRASS_LOCKABLE_SURCHARGE_GRATE`
  - `valve_mechanism`: `SWING_FLAPPER_NON_RETURN`, `DUAL_BALL_FLOAT_BACKWATER`, `NONE_GRAVITY_OPEN`
  - `min_freeboard_clearance_mm`: Vertical freeboard above finished ground (mm)
  - `position`: Snapped `(x, y)` coordinate
- `parse_sewer_reflux_valve_org_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceSewerRefluxValveOrgShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
