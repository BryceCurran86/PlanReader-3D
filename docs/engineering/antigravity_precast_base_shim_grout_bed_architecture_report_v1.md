# Architecture Report v1: Source Precast Concrete Panel Base Shim Pack & Structural Grout Bed Shadow Authority

## 1. Problem Statement & Scope
Precast tilt-up and architectural/structural concrete wall panels require precise temporary support on levelling shim packs and permanent load transfer through high-strength non-shrink cementitious grout beds beneath the base joint. In legacy extractions, panel base details often conflate levelling shims with permanent bearing pads or omit the minimum grout bed thickness (typically 20mm–50mm) and high compressive strength requirements (60–80 MPa), leading to unverified takeoff figures and inaccurate structural assembly models.

This module introduces `SourcePrecastBaseShimGroutBedShadowAuthority` to extract and validate panel base grout bed callouts, shim pack configurations, grout placement methods (dry-pack vs flowable dual-expansion non-shrink), and foam backer containment details strictly in shadow candidate mode.

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
- `PrecastBaseShimGroutBedCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `grout_bed_thickness_mm`: Thickness of grout joint (mm)
  - `shim_pack_type`: `PLASTIC_HORSESHOE_SHIM`, `STEEL_PACKER_PLATE`, `ELASTOMERIC_BEARING_PAD`, etc.
  - `shim_dimensions_mm`: Tuple of (width, length) or (100.0, 100.0)
  - `grout_strength_mpa`: Minimum 28-day compressive strength (MPa)
  - `grout_placement_method`: `DRY_PACK_MORTAR`, `FLOWABLE_FLUID_GROUT`, `PRESSURE_PUMPED`, etc.
  - `containment_backer`: `FOAM_BACKER_ROD`, `GROUT_FOAM_TAPE`, `TIMBER_STOP`, `UNSPECIFIED`
  - `position`: Snapped `(x, y)` coordinate
- `parse_precast_base_shim_grout_bed_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourcePrecastBaseShimGroutBedShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
