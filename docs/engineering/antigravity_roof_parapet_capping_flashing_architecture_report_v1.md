# Architecture Report: Source Roof Parapet Capping & Standing Seam Flashing Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Architectural roof drainage, parapet weatherproofing, and building envelope details.
- **Subsystem**: Parapet metal capping, standing seam counter-flashing, apron flashing, saddle flashing, and drip edges.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_roof_parapet_capping_flashing_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `PARAPET CAPPING`, `METAL CAPPING`, `STANDING SEAM FLASHING`, `APRON FLASHING`, `COUNTER FLASHING`, `PARAPET FLASHING`, `ROOF CAPPING`, `DRIP EDGE FLASHING`.
- **Flashing Types**:
  - `PARAPET_CAPPING` (e.g. metal cap over masonry/concrete/lightweight parapet)
  - `STANDING_SEAM_FLASHING` (e.g. zinc/copper/steel standing seam joint or upstand)
  - `COUNTER_FLASHING` (e.g. reglet-cut wall counter-flashing)
  - `APRON_FLASHING` (e.g. transition from roof sheeting to vertical upstand)
  - `DRIP_EDGE` (e.g. perimeter overhang drip edge)
- **Extracted Attributes**:
  - `material`: COLORBOND_STEEL, ZINC, ALUMINIUM, COPPER, STAINLESS_STEEL
  - `thickness_mm`: e.g. 0.55mm, 0.70mm, 1.0mm, 1.2mm
  - `girth_or_width_mm`: e.g. 300mm, 450mm, 600mm
  - `fall_slope_pct`: e.g. 3.0%, 5.0% fall inward to roof
  - `fixing_method`: CONTINUOUS_CLEAT, SCREW_FIXED, POP_RIVETED

## 3. Geometric Model
- Linear alignment polylines snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_rcf_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering flashing types, thickness/material detection, slope/fall parsing, snapping, dictionary export, safety caps, and invariance.
