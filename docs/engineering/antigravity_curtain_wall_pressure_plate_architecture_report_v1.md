# Architecture Report: Source Glazed Aluminium Curtain Wall Pressure Plate & Thermal Break Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Building envelope, curtain wall facade engineering (AAMA 501 / AS/NZS 4284 / CWCT).
- **Subsystem**: Pressure plates, continuous thermal break isolators, exterior snap-on feature caps, and IGU glazing pockets.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_curtain_wall_pressure_plate_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `CURTAIN WALL PRESSURE PLATE`, `PRESSURE PLATE`, `THERMAL BREAK`, `THERMALLY BROKEN MULLION`, `SNAP-ON CAP`, `BEAUTY CAP`, `CURTAIN WALL CAP`, `FACADE PRESSURE BAR`.
- **Thermal Isolator Type**:
  - `POLYAMIDE_STRUT` (e.g. Technoform continuous polyamide 6.6 with 25% glass fiber)
  - `RIGID_PVC_ISOLATOR`
  - `EPDM_ISOLATOR_GASKET`
- **Exterior Cap Profile**:
  - `RECTANGULAR_BOX_CAP`
  - `AEROFOIL_FEATURE_CAP`
  - `BULLNOSE_CAP`
  - `FLUSH_SEAL_NO_CAP`
- **Extracted Attributes**:
  - `mullion_depth_mm`: e.g. 150mm, 175mm, 200mm, 225mm
  - `mullion_sightline_width_mm`: e.g. 50mm, 65mm
  - `glazing_pocket_mm`: e.g. 28mm, 32mm, 36mm, 42mm (for double/triple IGU)
  - `cap_projection_depth_mm`: e.g. 15mm, 50mm, 100mm, 150mm
  - `pressure_screw_pitch_mm`: e.g. 200mm, 250mm, 300mm CTS

## 3. Geometric Model
- Curtain wall linear grid polyline snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_cwp_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering thermal break types, cap profiles, mullion depths, IGU pockets, screw pitch, polyline snapping, dictionary serialization, and customer retention verification.
