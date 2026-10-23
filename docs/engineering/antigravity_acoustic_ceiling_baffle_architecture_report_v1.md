# Architecture Report v1: Source Acoustic Ceiling Baffle Suspended Absorber Shadow Authority

## 1. Problem Statement & Scope
Open-plenum commercial ceilings (offices, lobbies, cafeterias, and auditoriums) utilize suspended vertical acoustic baffles (PET polyester fiber, fabric-wrapped fiberglass, or micro-perforated timber/metal) to reduce reverberation time (RT60) while maintaining open airflow and sprinkler distribution. In legacy extractions, ceiling baffles were often conflated with continuous suspended grid ceilings or dropped altogether, omitting essential acoustic ratings (NRC 0.70–0.95), baffle dimensions (length x depth), on-center spacing (mm), and suspension hardware required for ceiling takeoff and MEP coordination.

This module introduces `SourceAcousticCeilingBaffleShadowAuthority` to extract and validate suspended acoustic ceiling baffle callouts, absorber materials, sound absorption NRC ratings, baffle thicknesses and dimensions (length x depth), on-center pitch, and suspension hardware strictly in shadow candidate mode.

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
- `AcousticCeilingBaffleCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `baffle_material`: `POLYESTER_FIBER_PET`, `GLASSWOOL_RESIN_BONDED`, `TIMBER_SLAT_PERFORATED`, `ALUMINIUM_BAFFLE_MICRO_PERF`
  - `nrc_sound_absorption`: Noise reduction coefficient (e.g. 0.85, 0.90)
  - `baffle_thickness_mm`: Baffle thickness in mm (e.g. 12.0, 24.0, 50.0)
  - `baffle_dimensions_mm`: Tuple of `(length, depth)` in mm (e.g. 2400.0, 300.0)
  - `suspension_method`: `ADJUSTABLE_AIRCRAFT_WIRE`, `THREADED_ROD_SUSPENSION`, `DIRECT_UNISTRUT_CHANNEL`, etc.
  - `center_spacing_mm`: On-center spacing pitch in mm (e.g. 200.0, 300.0)
  - `position`: Snapped `(x, y)` coordinate
- `parse_acoustic_ceiling_baffle_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceAcousticCeilingBaffleShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
