# Architecture Report: Source Cast-In Concrete Starter Bar Dowel Box & Pull-Out Rebend Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Structural reinforced concrete engineering (AS 3600 Section 13 / Eurocode 2 / ACI 318 construction joints).
- **Subsystem**: Cast-in starter bar pull-out rebend boxes, continuous dowel casings, and slab-to-core-wall reinforcement continuity systems.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_starter_bar_rebend_box_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `STARTER BAR BOX`, `REBEND BOX`, `PULL-OUT BAR`, `DOWEL BOX`, `REIDBOX`, `EAZISTRIP`, `BARTEC BOX`, `CONTINUITY STRIP BOX`.
- **Bar Row Configuration**:
  - `SINGLE_ROW` (single layer of pull-out rebar)
  - `DOUBLE_ROW` (two layers of pull-out rebar)
- **Extracted Attributes**:
  - `bar_diameter_mm`: e.g. 12mm (N12), 16mm (N16), 20mm (N20)
  - `bar_spacing_mm`: e.g. 150mm, 200mm, 250mm CTS
  - `casing_width_mm`: e.g. 100mm, 150mm, 170mm, 200mm
  - `pull_out_lap_length_mm`: e.g. 450mm, 500mm, 600mm
  - `joint_location`: SLAB_TO_WALL, WALL_TO_SLAB, WALL_TO_WALL

## 3. Geometric Model
- Joint alignment run polyline snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_sbb_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering row configurations, bar diameters, spacing, casing widths, lap lengths, polyline snapping, dictionary serialization, and customer retention verification.
