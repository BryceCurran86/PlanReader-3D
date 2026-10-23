# Architecture Report v1: Source Roof Parapet Overflow Scupper & Chute Shadow Authority

## 1. Problem Statement & Scope
Box gutters enclosed by exterior parapet walls require dedicated secondary emergency overflow scuppers or discharge chutes compliant with AS/NZS 3500.3 / IBC Section 1503.4 to prevent structural roof collapse from catastrophic hydraulic ponding when primary rainwater downpipes become obstructed by storm debris. In architectural elevation and parapet detail drawings, overflow scuppers are often misclassified as simple weep holes or decorative facade reveals.

This module introduces `SourceParapetOverflowScupperShadowAuthority` to extract and validate roof parapet overflow scuppers, chute dimensions (width x height mm), invert elevation above gutter sole (mm), discharge overflow capacity (L/s), sheet metal lining material (Colorbond, stainless steel, copper), and emergency discharge free fall clearances strictly in shadow candidate mode.

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
- `ParapetOverflowScupperCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `scupper_type`: `PARAPET_WALL_OPEN_CHUTE_SCUPPER`, `CONCEALED_OVERFLOW_WEIR_BOX`, `THROUGH_WALL_OVERFLOW_SLEEVE`
  - `width_mm`: Clear weir opening width (mm)
  - `height_mm`: Clear opening height (mm)
  - `invert_elevation_above_sole_mm`: Invert height above box gutter base (mm)
  - `overflow_capacity_lps`: Rated overflow flow rate in L/s
  - `sheet_metal_material`: `COLORBOND_STEEL`, `STAINLESS_STEEL_316`, `COPPER_SHEET`
  - `position`: Snapped `(x, y)` coordinate
- `parse_parapet_overflow_scupper_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceParapetOverflowScupperShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
