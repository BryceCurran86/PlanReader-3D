# Architecture Report v1: Source Civil Stormwater Silt Arrestor Pit & Ductile Iron Grate Shadow Authority

## 1. Problem Statement & Scope
Civil and external site drainage designs mandate stormwater silt arrestor pits (sediment collection pits) equipped with permanent submerged sump storage zones (typically 300mm - 600mm below pipe invert), oil/trash baffle hoods, and vehicular-rated ductile iron grates (Class B to Class D compliant with AS 3996 / EN 124) to trap coarse sediment, grit, and road pollutants before discharge into municipal trunk drainage or on-site detention basins. In civil drawings, silt pits are often confused with standard junction pits, omitting critical silt storage volumes and load class requirements.

This module introduces `SourceStormwaterSiltArrestorPitShadowAuthority` to extract and validate stormwater silt arrestor pits, pit internal dimensions (length x width x depth mm), sump silt storage volume (litres), outlet pipe invert drops, load classifications (Class A to Class D), and trash/oil baffle weir hoods strictly in shadow candidate mode.

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
- `StormwaterSiltArrestorPitCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `pit_type`: `PRECAST_CONCRETE_SILT_PIT`, `CAST_IN_SITU_SEDIMENT_SUMP_PIT`, `POLYETHYLENE_SILT_ARRESTOR`
  - `internal_length_mm`: Clear internal pit length (mm)
  - `internal_width_mm`: Clear internal pit width (mm)
  - `sump_depth_below_invert_mm`: Silt storage sump depth below outlet pipe invert (mm)
  - `grate_load_class`: `CLASS_B_CAR_PARK`, `CLASS_D_HEAVY_DUTY_ROADWAY`, `CLASS_A_PEDESTRIAN`
  - `baffle_weir_included`: Boolean indicating submerged oil/trash baffle hood
  - `position`: Snapped `(x, y)` coordinate
- `parse_stormwater_silt_arrestor_pit_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceStormwaterSiltArrestorPitShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
