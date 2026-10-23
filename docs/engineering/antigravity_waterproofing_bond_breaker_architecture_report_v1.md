# Architecture Report v1: Source Wet Area Waterproofing Membrane & Bond Breaker Fillet Shadow Authority

## 1. Problem Statement & Scope
Internal wet areas (bathrooms, ensuites, laundries, powder rooms) and external balconies require liquid-applied or sheet waterproofing membranes compliant with AS 3740 / AS 4654.2 / IBC Section 1210. Critical to membrane performance is the continuous installation of elastomeric neutral-cure silicone or polyurethane bond breaker fillets (typically 12x12mm cove fillet or Class III bond breaker tape) at all internal 90° floor-to-wall junctions, hob-to-wall perimeters, and vertical movement joints, with minimum mandatory vertical upturns (typically 150mm - 1800mm in shower enclosures). In architectural finishes plans and wet area details, bond breaker fillets and membrane class ratings are often omitted or conflated with tile finish borders.

This module introduces `SourceWaterproofingBondBreakerShadowAuthority` to extract and validate wet area waterproofing membranes, membrane classification (Class I, II, III liquid polyurethane / acrylic / sheet), bond breaker fillet dimensions (mm), vertical wall upturn heights (mm), dry film thickness (DFT mm), and shower hob flashing details strictly in shadow candidate mode.

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
- `WaterproofingBondBreakerCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `membrane_class`: `CLASS_III_HIGH_EXTENSIBILITY_LIQUID`, `CLASS_II_MEDIUM_EXTENSIBILITY`, `PREFORMED_SHEET_MEMBRANE`
  - `bond_breaker_type`: `ELASTOMERIC_POLYURETHANE_COVE_FILLET`, `NEUTRAL_CURE_SILICONE_FILLET`, `REINFORCING_BOND_BREAKER_TAPE`
  - `fillet_size_mm`: Fillet leg dimension (e.g. 12.0 mm)
  - `upturn_height_mm`: Vertical upturn termination height above finished floor (mm)
  - `dry_film_thickness_dft_mm`: Nominal dry film thickness in mm
  - `hob_detail`: `MASONRY_HOB_WATERPROOFED`, `FLUSH_RECESS_STEPDOWN`, `NO_HOB_LEVEL_THRESHOLD`
  - `position`: Snapped `(x, y)` coordinate
- `parse_waterproofing_bond_breaker_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceWaterproofingBondBreakerShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
