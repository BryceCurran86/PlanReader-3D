# Architecture Report v1: Source Structural Timber Roof Truss Tie-Down & Framing Anchor Shadow Authority

## 1. Problem Statement & Scope
Residential and commercial timber roof framing requires engineered tie-down connections (framing anchors, triple grips, cyclone straps, multi-grip brackets) between prefabricated gang-nail roof trusses and wall top plates to resist cyclonic and non-cyclonic wind uplift pressures (N1-N4, C1-C4). In structural roof framing plans and tie-down schedules, these brackets are often obscured by truss centerline layout chords or conflated with generic framing nails.

This module introduces `SourceTrussTieDownShadowAuthority` to extract and validate roof truss tie-down brackets, bracket types (triple grip, framing anchor, cyclone strap, unities), fastener types/counts (e.g. 4 x 30x2.8mm nails per leg), characteristic design uplift capacities (kN), and wind classification ratings strictly in shadow candidate mode.

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
   - Deterministic keyword and regex extraction without benchmark dependencies.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `TrussTieDownCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `bracket_type`: `TRIPLE_GRIP_FRAMING_ANCHOR`, `CYCLONE_TIE_DOWN_STRAP`, `MULTI_GRIP_UNIVERSAL_BRACKET`, `TRUSS_BOOT_INTERNAL_BRACKET`
  - `wind_rating`: `WIND_CLASS_N2_N3`, `WIND_CLASS_N4_C1`, `WIND_CLASS_C2_C3_CYCLONIC`
  - `fastener_description`: Fastener size & quantity (e.g. `4_NAILS_30X2_8MM_PER_LEG`)
  - `characteristic_uplift_kn`: Design wind uplift limit (kN)
  - `strap_gauge_mm`: Sheet steel bracket gauge (mm)
  - `position`: Snapped `(x, y)` coordinate
- `parse_truss_tie_down_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceTrussTieDownShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
