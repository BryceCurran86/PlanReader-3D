# Architecture Report v1: Source Underground Subsoil Ag Drain & Geotextile Sock Shadow Authority

## 1. Problem Statement & Scope
Subsurface drainage networks around basement perimeter retaining walls, footing beams, and civil pavement subgrades require corrugated perforated slotted agricultural drainage pipes (ag-pipe) encased in non-woven needle-punched geotextile filter socks and washed aggregate drainage gravel envelopes. In civil and structural drawing annotations, subsoil ag drains are frequently omitted or conflated with solid PVC sewer/stormwater pipes, leading to missing geotextile filter sock specifications and gravel backfill volumes.

This module introduces `SourceSubsoilAgDrainGeotextileShadowAuthority` to extract and validate underground subsoil agricultural drainage runs, pipe diameters (DN65 - DN160), slotted vs unslotted perforation patterns, class stiffness (Class 400 / 1000), geotextile filter sock mass (g/m2), and gravel backfill envelope depths strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Coordinate Snapping**:
   - Snapped with `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
4. **Zero Gold Dependencies**:
   - Pure regex and keyword parsing without benchmark gold dependencies.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `SubsoilAgDrainGeotextileCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `pipe_diameter_dn`: Nominal size (e.g. `DN65`, `DN100`, `DN160`)
  - `pipe_profile`: `SLOTTED_PERFORATED_CORRUGATED`, `UNSLOTTED_CARRIER`, `SMOOTH_BORE_PERFORATED`
  - `class_stiffness`: `CLASS_400_STANDARD`, `CLASS_1000_HEAVY_DUTY`
  - `geotextile_filter_sock`: `NON_WOVEN_GEOTEXTILE_FILTER_SOCK`, `SEAMLESS_KNITTED_POLYESTER_SLEEVE`, `NONE_GRAVEL_SURROUND_ONLY`
  - `gravel_backfill_depth_mm`: Aggregate filter drainage bed depth (mm)
  - `position`: Snapped `(x, y)` coordinate
- `parse_subsoil_ag_drain_geotextile_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceSubsoilAgDrainGeotextileShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
