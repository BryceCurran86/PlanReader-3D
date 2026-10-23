# Architecture Report: Source Electrical Cable Ladder Unistrut Trapeze Hanger Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Electrical containment systems, power distribution pathways (AS/NZS 3000 / AS/NZS 3013 / NEMA VE 1).
- **Subsystem**: Heavy-duty cable ladders, unistrut slotted steel channel trapeze hangers, threaded drop rods, seismic sway braces, and fire ratings.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_cable_ladder_trapeze_hanger_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `CABLE LADDER`, `TRAPEZE HANGER`, `UNISTRUT HANGER`, `ELECTRICAL LADDER`, `CABLE TRAY HANGER`, `HEAVY DUTY LADDER`, `NEMA LADDER`.
- **Ladder Material & Finish**:
  - `HOT_DIP_GALVANIZED` (HDG)
  - `STAINLESS_STEEL_316`
  - `ALUMINIUM`
  - `PRE_GALVANIZED`
- **Extracted Attributes**:
  - `ladder_width_mm`: e.g. 150, 300, 450, 600, 900mm
  - `side_rail_height_mm`: e.g. 75mm, 100mm, 125mm, 150mm
  - `channel_profile`: P1000 (41x41), P2000 (41x21), P1001 (double 41x82)
  - `threaded_rod_dia_mm`: e.g. M10, M12, M16
  - `hanger_spacing_mm`: e.g. 1500mm, 2000mm, 3000mm CTS
  - `fire_rated`: True/False (e.g. AS/NZS 3013 2-hour rating)
  - `seismic_sway_bracing`: True/False

## 3. Geometric Model
- Centerline alignment polylines snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_clt_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering ladder widths, rail heights, unistrut channels, rod sizes, fire ratings, seismic bracing, polyline snapping, dictionary serialization, and customer retention verification.
