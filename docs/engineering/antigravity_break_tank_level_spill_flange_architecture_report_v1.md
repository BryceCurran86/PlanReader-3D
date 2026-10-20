# Architecture Report v1: Source Cold Water Storage Tank Break Tank Level Transmitter & Spill Flange Shadow Authority

## 1. Problem Statement & Scope
Cold water break tanks and domestic potable/non-potable storage tanks require strict physical backflow prevention (Type AA or AB air gaps) via engineered overflow spill flanges, coupled with electronic continuous level transmitters (hydrostatic, ultrasonic, or guided-wave radar) and high-level alarm switches to prevent pump cavitation and tank overflowing. In legacy extractions, tank schedule items were frequently collapsed to raw volumes, dropping spill flange sizes, air gap classifications, and transmitter sensor types required for hydraulic authority signoff.

This module introduces `SourceBreakTankLevelSpillFlangeShadowAuthority` to extract and validate water break tank callouts, storage capacities (litres), continuous level transmitters, spill/overflow flange sizes (DN), and regulatory air gap types strictly in shadow candidate mode.

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
- `BreakTankLevelSpillFlangeCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `tank_type`: `BREAK_TANK_POTABLE`, `NON_POTABLE_RAINWATER_TANK`, `FIRE_WATER_STORAGE_TANK`, `HEADER_TANK`
  - `effective_capacity_litres`: Storage capacity in litres
  - `level_transmitter_type`: `HYDROSTATIC_SUBMERSIBLE_PRESSURE`, `ULTRASONIC_NON_CONTACT`, `RADAR_GUIDED_WAVE`, etc.
  - `overflow_spill_flange_dn`: Nominal diameter of overflow flange (e.g. `DN100`, `DN150`, `DN200`)
  - `air_gap_type`: `TYPE_AA_AIR_GAP`, `TYPE_AB_NON_CIRCULAR_OVERFLOW`, `TYPE_AF_DROPLET_AIR_GAP`, `AIR_BREAK_UNSPECIFIED`
  - `position`: Snapped `(x, y)` coordinate
- `parse_break_tank_level_spill_flange_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceBreakTankLevelSpillFlangeShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
