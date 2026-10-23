# Architecture Report: Source Hydraulic Stormwater Sump Silt Trap & Floating Oil Skimmer Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Civil / hydraulic stormwater engineering (AS 3500.3 / local water authority standards), site drainage water quality management.
- **Subsystem**: Stormwater catchment pits, silt/sediment retention sumps, trash screens, and floating oil skimmers / coalescing separator baffles.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_stormwater_silt_trap_skimmer_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `SILT TRAP`, `STORMWATER SUMP`, `SEDIMENT TRAP`, `OIL SKIMMER`, `COALESCING PLATE`, `HYDROCARBON BAFFLE`, `SUMP PIT SILT`, `STORMWATER SILT PIT`.
- **Skimmer / Separator Device Types**:
  - `FLOATING_WEIR_SKIMMER` (floating oil absorption/skimming weir)
  - `COALESCING_PLATE_PACK` (inclined corrugated plate pack)
  - `HYDROCARBON_BAFFLE` (under-flow dip baffle plate)
  - `SEDIMENT_SUMP_ONLY` (passive sediment drop chamber without active oil skimmer)
- **Extracted Attributes**:
  - `pit_dimensions_mm`: e.g. "900x900", "1200x1200", "1500x1500"
  - `silt_storage_depth_mm`: Depth below pipe invert (e.g. 300mm, 450mm, 600mm)
  - `trash_screen_present`: True/False (removable stainless steel basket)
  - `grate_class`: CLASS_D (trafficable), CLASS_B (light/pedestrian), SOLID_COVER

## 3. Geometric Model
- Sump centroid point coordinates `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_sts_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering skimmer device types, pit dimensions, silt depth parsing, grate classes, point snapping, dictionary serialization, and customer retention verification.
