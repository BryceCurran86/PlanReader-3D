# Architecture Report v1: Source Acoustic Floating Floor Sylomer Isolation Bearing Pad Shadow Authority

## 1. Problem Statement & Scope
High-performance acoustic floating floor slabs in plant rooms, recording studios, cinemas, and fitness centers require discrete cellular polyurethane elastomer bearing pads (Sylomer / Sylodyn) to decouple dynamic impact and structure-borne vibration from structural base slabs. In legacy extractions, acoustic isolation pads were often confused with generic expansion joint foam or neglected entirely, omitting the specific elastomer grade (e.g., SR 11, SR 28, SR 55), pad thickness (12.5mm–50mm), and natural resonance frequency (Hz) required to verify acoustic compliance.

This module introduces `SourceAcousticSylomerBearingPadShadowAuthority` to extract and validate acoustic floating floor isolation pad callouts, Sylomer material grades, static load capacities (N/mm²), natural frequencies (Hz), pad dimensions, and perimeter flanking strips strictly in shadow candidate mode.

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
- `AcousticSylomerBearingPadCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `sylomer_grade`: Grade code (e.g. `SYLOMER_SR11`, `SYLOMER_SR28`, `SYLOMER_SR55`, `SYLODYN_NC`)
  - `static_range_n_per_mm2`: Nominal static load rating in N/mm²
  - `pad_thickness_mm`: Thickness in mm (e.g. 12.5, 25.0, 50.0)
  - `pad_dimensions_mm`: Tuple of `(width, length)` in mm
  - `natural_frequency_hz`: Natural frequency in Hz (e.g. 8.0, 10.0, 12.0)
  - `air_cavity_depth_mm`: Air void cavity depth in mm
  - `perimeter_isolation`: `PERIMETER_ISOLATION_STRIP`, `RESILIENT_CAULKING`, `NONE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_acoustic_sylomer_bearing_pad_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceAcousticSylomerBearingPadShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
