# Architecture Report v1: Source Rainwater Harvesting First Flush Diverter Shadow Authority

## 1. Problem Statement & Scope
Rainwater harvesting networks mandate first flush diversion mechanisms to prevent initial roof contaminants, atmospheric particulates, and organic sediment from entering underground detention or rainwater harvesting storage tanks. In MEP and civil drawing extractions, first flush devices are frequently misidentified as generic stormwater downpipes, gullies, or standard PVC pipe bends.

This module introduces `SourceFirstFlushDiverterShadowAuthority` to extract and validate first flush diverter assemblies, chamber volumes (litres), nominal pipe diameters (DN90 - DN300), auto-drain slow-release bleed valves, and leaf screen filter mesh ratings strictly in shadow candidate mode.

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
   - Pure deterministic regex and keyword parsing without benchmark-specific biases.
5. **Customer Baseline Invariance**:
   - Operates in strict isolation from customer gold baselines.

## 3. Authority Interface
- `FirstFlushDiverterCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `pipe_diameter_dn`: Nominal size (e.g. `DN100`, `DN150`, `DN225`)
  - `chamber_volume_litres`: Diverter collection volume in litres (L)
  - `diverter_type`: `IN_GROUND_VERTICAL_CHAMBER`, `WALL_MOUNTED_POST_DOWNPIPE`, `COMMERCIAL_HIGH_VOLUME`
  - `drain_bleed_mechanism`: `SLOW_RELEASE_BLEED_CONTROL_VALVE`, `ELECTRONIC_TIMER_PURGE`, `MANUAL_DRAIN_VALVE`
  - `filter_mesh_screen_type`: `STAINLESS_STEEL_LEAF_EATER_SCREEN`, `PRIMARY_MESH_CAGE`, `INTEGRAL_BALL_FLOAT`
  - `position`: Snapped `(x, y)` coordinate
- `parse_first_flush_diverter_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceFirstFlushDiverterShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
