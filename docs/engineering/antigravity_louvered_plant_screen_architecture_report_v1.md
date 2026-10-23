# Architecture Report v1: Source External Louvered Equipment Screen Plant Deck Shadow Authority

## 1. Problem Statement & Scope
Rooftop mechanical plant decks and outdoor equipment compounds require external louvered visual and acoustic screening to conceal chillers, condenser units, cooling towers, and exhaust fans from sight while ensuring required aerodynamic free ventilation area (typically 45%–60%) and wind-load structural resistance. In previous extractions, plant deck screening was frequently confused with standard wall cladding or internal louvers, dropping total screen heights (1800mm–3000mm), support post profiles (e.g., steel SHS vs aluminium box mullions), and free ventilation area percentages necessary for mechanical airflow modeling.

This module introduces `SourceLouveredPlantScreenShadowAuthority` to extract and validate rooftop/compound equipment screen callouts, blade profiles, aerodynamic free ventilation percentages, visual occlusion ratings, overall heights, structural support posts, and architectural finishes strictly in shadow candidate mode.

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
- `LouveredPlantScreenCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `screen_profile`: `CONTINUOUS_HORIZONTAL_LOUVER`, `ACOUSTIC_LOUVER_SCREEN`, `VERTICAL_SLAT_SCREEN`, `CHEVRON_VISUAL_SCREEN`
  - `blade_free_area_percent`: Percentage of aerodynamic free open area (e.g. 50.0%)
  - `overall_height_mm`: Total screen height in mm (e.g. 2400.0)
  - `structural_support_post`: `STEEL_SHS_POST`, `ALUMINIUM_BOX_POST`, `C-CHANNEL_MULLION`, etc.
  - `visual_screening_percent`: Percentage of sightline blockage (e.g. 100.0%)
  - `finish_specification`: `POWDER_COATED_DULUX`, `ANODIZED_25UM`, `HOT_DIP_GALVANIZED`, etc.
  - `position`: Snapped `(x, y)` coordinate
- `parse_louvered_plant_screen_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceLouveredPlantScreenShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
