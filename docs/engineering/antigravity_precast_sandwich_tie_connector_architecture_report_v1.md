# Architecture Report: Source Precast Concrete Insulated Sandwich Panel Tie Connector Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Precast insulated sandwich wall panels (architectural and structural precast).
- **Subsystem**: Composite wythe tie connectors (GFRP pins, stainless steel truss ties, carbon fiber grid, cylinder sleeve pins) connecting structural inner wythe, continuous insulation core (PIR/XPS/EPS), and exterior fascia wythe.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_precast_sandwich_tie_connector_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `SANDWICH PANEL TIE`, `INSULATED PANEL TIE`, `GFRP CONNECTOR`, `FIBERGLASS PIN`, `THERMOMASS`, `COMPOSITE TIE`, `TRUSS TIE`, `WYTHE CONNECTOR`.
- **Connector Types**:
  - `GFRP_PIN_CONNECTOR` (e.g. Thermomass, fiberglass composite rod/pin)
  - `STAINLESS_TRUSS_TIE` (e.g. 316 stainless steel zig-zag or truss connector)
  - `CARBON_FIBER_GRID` (e.g. C-GRID composite mesh)
  - `CYLINDER_SLEEVE_PIN` (e.g. high-shear polymer / fiber sleeve)
- **Extracted Attributes**:
  - `outer_wythe_thickness_mm`: Exterior concrete wythe (e.g. 75mm, 80mm)
  - `insulation_thickness_mm`: Rigid insulation core (e.g. 50mm, 75mm, 100mm)
  - `inner_wythe_thickness_mm`: Structural concrete wythe (e.g. 150mm, 175mm, 200mm)
  - `spacing_mm`: Grid spacing (e.g. 400mm, 600mm CTS)
  - `insulation_type`: PIR, XPS, EPS, or MINERAL_WOOL

## 3. Geometric Model
- Discrete connector point coordinates `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_spt_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests verifying callout classification, wythe thickness parsing, insulation type detection, coordinate snapping, serialization, safety cap enforcement, and invariance.
