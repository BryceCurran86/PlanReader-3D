# Architecture Report v1: Source Structural Steel Purlin Apex Tie & Ridge Cleat Shadow Authority

## 1. Problem Statement & Scope
Cold-formed C and Z roof purlins converging at the roof ridge line require specialized apex ties and ridge cleats to prevent purlin roll, unbraced flange buckling, and apex joint separation under wind uplift and gravity roof loads. Previous extraction routines frequently dropped ridge purlin details or confused apex strap ties with standard bridging rows, omitting the cleat plate gauge (typically 3mm to 6mm) and bolting details required for structural engineering checks.

This module introduces `SourceSteelPurlinApexTieShadowAuthority` to extract and validate roof purlin apex ties, ridge cleat brackets, roof pitch angles, purlin profiles, bolt fasteners, and corrosion protection coatings strictly in shadow candidate mode.

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
- `SteelPurlinApexTieCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `purlin_section`: Section designation (e.g. `C20015`, `Z20020`, `C15015`)
  - `apex_tie_type`: `STRAP_APEX_TIE`, `ANGLE_APEX_STRUT`, `SOLID_ROD_APEX_TIE`, `CHANNEL_RIDGE_BRACE`
  - `ridge_cleat_gauge_mm`: Thickness of ridge cleat bracket in mm (e.g. 3.0, 4.0, 6.0)
  - `bolt_specification`: Bolt fastener callout (e.g. `M12 GR4.6`, `2-M12 BOLTS`)
  - `pitch_degrees`: Roof pitch in degrees (e.g. 5.0, 10.0, 15.0)
  - `coating_finish`: `GALVABOND_Z450`, `HOT_DIP_GALVANIZED`, `ZINCALUME`, `UNSPECIFIED`
  - `position`: Snapped `(x, y)` coordinate
- `parse_steel_purlin_apex_tie_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceSteelPurlinApexTieShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
