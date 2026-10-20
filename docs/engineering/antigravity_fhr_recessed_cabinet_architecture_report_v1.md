# Architecture Report v1: Source Fire Hose Reel Cabinet Recessed Thermally Insulated Door Shadow Authority

## 1. Problem Statement & Scope
Fire hose reel (FHR) cabinets embedded in fire-rated wall assemblies (such as drywall shafts, masonry cores, and corridor fire barriers) require specialized recessed enclosures with thermally insulated, fire-resistant doors to maintain barrier integrity (e.g., -/60/60 or -/120/120 FRL) and prevent heat transmission to adjacent escape routes. Previous extraction routines often failed to differentiate between surface-mounted uninsulated sheetmetal boxes and fully recessed cabinets with rockwool/mineral fiber insulation cores and intumescent perimeter seals, leading to wall penetration compliance gaps.

This module introduces `SourceFhrRecessedCabinetShadowAuthority` to extract and validate FHR cabinet callouts, mounting configurations (recessed, semi-recessed, surface), door construction, thermal insulation cores, and fire-resistance ratings strictly in shadow candidate mode.

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
- `FhrRecessedCabinetCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `mounting`: `FULLY_RECESSED`, `SEMI_RECESSED`, `SURFACE_MOUNTED`
  - `door_type`: `SOLID_FLUSH_INSULATED`, `GLAZED_VISION_PANEL`, `BREAK_GLASS`, `STAINLESS_STEEL`, etc.
  - `insulation_core`: `ROCKWOOL_INSULATION`, `MINERAL_FIBER`, `CERAMIC_BLANKET`, `NONE`
  - `frl_minutes`: Fire-resistance rating in minutes (e.g. 60, 120, 0)
  - `hose_length_m`: Hose reel length in meters (e.g. 36.0, 50.0)
  - `dimensions_mm`: Tuple of `(width, height, depth)` in mm
  - `position`: Snapped `(x, y)` coordinate
- `parse_fhr_recessed_cabinet_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceFhrRecessedCabinetShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
