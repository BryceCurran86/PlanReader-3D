# Architecture Report: Source Acoustic Wall Fabric Baffle & Resilient Channel Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Architectural acoustics, sound absorption and transmission loss (ISO 354 / ASTM C423 / AS ISO 354).
- **Subsystem**: Fabric-wrapped acoustic wall panels, vertical/horizontal sound absorbing baffles, and resilient mounting channels (RC-1 / RC-2 / acoustic isolation clips).
- **Authority Type**: Shadow candidate extraction authority (`pb_source_acoustic_fabric_baffle_resilient_channel_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `ACOUSTIC WALL PANEL`, `FABRIC BAFFLE`, `RESILIENT CHANNEL`, `RC-1 CHANNEL`, `ACOUSTIC BAFFLE`, `FABRIC WRAPPED PANEL`, `SOUND ABSORBING PANEL`, `ACOUSTIC WALL LINING`.
- **Panel Core Material**:
  - `FIBERGLASS_CORE` (e.g. 96 kg/m³ high-density resin-bonded glasswool)
  - `POLYESTER_FIBRE` (e.g. semi-rigid polyester acoustic board)
  - `ACOUSTIC_FOAM` (e.g. open-cell melamine foam)
  - `TIMBER_ACOUSTIC_SLAT` (e.g. slotted/perforated timber veneer)
- **Extracted Attributes**:
  - `panel_thickness_mm`: e.g. 25mm, 50mm, 75mm
  - `nrc_rating`: e.g. 0.85, 0.90, 0.95, 1.00
  - `resilient_channel_type`: RC_1_SINGLE_LEG, RC_2_DOUBLE_LEG, RESILIENT_CLIP, DIRECT_ADHESIVE
  - `channel_spacing_mm`: e.g. 400mm, 600mm CTS
  - `fabric_finish`: ACOUSTIC_TEXTILE, PERFORATED_VINYL, UNFINISHED

## 3. Geometric Model
- Wall lining polyline alignment snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_awb_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering panel materials, thicknesses, NRC parsing, resilient channel types, channel spacing, polyline snapping, dictionary serialization, and customer retention verification.
