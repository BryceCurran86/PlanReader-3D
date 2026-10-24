# Architecture Report v1: Source Seismic Restraint Cable Sway Brace MEP Suspended Services Shadow Authority

## 1. Problem Statement & Scope
Suspended MEP services (chilled water / condenser water piping, fire sprinkler mains, primary HVAC ductwork, and electrical cable trays) subject to seismic building code compliance (AS 1170.4 / NZS 4219 / IBC Chapter 13) require engineered transverse and longitudinal sway bracing. Previous extractions routinely dropped cable diameter specifications (e.g., 3.2mm–6.4mm 7x19 galvanized aircraft cable), brace orientation angles (30°–60°), seismic design accelerations (g), and substrate attachment anchors, resulting in severe compliance and structural clash blind spots.

This module introduces `SourceSeismicSwayBraceMepShadowAuthority` to extract and validate suspended MEP seismic sway brace callouts, transverse vs longitudinal cable orientations, cable diameters, installation angles, seismic design acceleration coefficients (g), and structural anchor details strictly in shadow candidate mode.

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
- `SeismicSwayBraceMepCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `brace_type`: `TRANSVERSE_CABLE_SWAY_BRACE`, `LONGITUDINAL_CABLE_SWAY_BRACE`, `4_WAY_RIGID_STRUT_BRACE`, `TENSION_ONLY_AIRCRAFT_CABLE`
  - `cable_diameter_mm`: Cable thickness in mm (e.g. 3.2, 4.8, 6.4)
  - `brace_angle_degrees`: Installation angle in degrees (e.g. 45.0)
  - `service_type`: `SUSPENDED_CHW_PIPE`, `FIRE_SPRINKLER_MAIN`, `RECTANGULAR_HVAC_DUCT`, `ELECTRICAL_CABLE_TRAY`
  - `seismic_design_acceleration_g`: Design horizontal acceleration in g (e.g. 0.25, 0.35)
  - `anchor_type`: `CONCRETE_EXPANSION_ANCHOR`, `STEEL_BEAM_CLAMP`, `THROUGH_BOLT_DECK`, `DROP_IN_ANCHOR`
  - `position`: Snapped `(x, y)` coordinate
- `parse_seismic_sway_brace_mep_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceSeismicSwayBraceMepShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
