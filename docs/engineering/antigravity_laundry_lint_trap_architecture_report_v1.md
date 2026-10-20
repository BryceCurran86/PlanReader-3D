# Architecture Report: Source Commercial Laundry Lint Trap & Hydrodynamic Interceptor Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Hydraulic trade waste drainage, commercial laundries and hospitality washhouses (AS 3500.2 / Water Utility Trade Waste Codes).
- **Subsystem**: Commercial laundry lint interceptors, dual perforated stainless steel filter baskets, airtight access lids, and sampling shafts.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_laundry_lint_trap_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `LINT TRAP`, `LAUNDRY INTERCEPTOR`, `LINT PIT`, `LINT SCREEN`, `TRADE WASTE LINT`, `COMMERCIAL LAUNDRY TRAP`, `HYDRODYNAMIC LINT`.
- **Trap Construction Material**:
  - `STAINLESS_STEEL_316` (e.g. fabricated grade 316 pit)
  - `ROTOMOULDED_POLYETHYLENE` (poly underground pit)
  - `PRECAST_CONCRETE` (heavy duty cast concrete pit)
- **Extracted Attributes**:
  - `capacity_litres`: e.g. 250L, 500L, 1000L, 1500L
  - `dual_filter_baskets`: True/False (coarse primary & fine secondary mesh)
  - `inlet_outlet_dia_mm`: e.g. 100mm, 150mm (DN100, DN150)
  - `cover_class`: CLASS_B_GASTIGHT, CLASS_D_GASTIGHT, BOLTED_AIRTIGHT
  - `sampling_point_present`: True/False

## 3. Geometric Model
- Lint pit centroid coordinates `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_llt_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering materials, capacities, dual baskets, pipe diameters, cover classes, coordinate snapping, dictionary serialization, and customer retention verification.
