# Architecture Report: Source Structural Concrete Corbels & Precast Beam Bearing Nibs Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Structural concrete engineering (AS 3600 / ACI 318 Section 23 Strut-and-Tie / Eurocode 2).
- **Subsystem**: Column corbels, wall brackets, dapped beam ends, and precast beam shelf nibs.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_concrete_corbel_bearing_nib_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `CONCRETE CORBEL`, `COLUMN CORBEL`, `BEAM NIB`, `DAPPED END`, `WALL BRACKET`, `BEARING NIB`, `PRECAST CORBEL`, `PRECAST BEARING NIB`.
- **Corbel / Bracket Configuration**:
  - `COLUMN_CORBEL` (e.g. projection from RC column)
  - `WALL_CORBEL` (e.g. continuous or discrete bracket on shear wall)
  - `DAPPED_BEAM_NIB` (e.g. recessed dapped end of precast girder)
- **Extracted Attributes**:
  - `projection_length_mm`: e.g. 250mm, 300mm, 350mm, 400mm
  - `root_depth_mm`: e.g. 350mm, 400mm, 500mm, 600mm
  - `width_mm`: e.g. 300mm, 350mm, 400mm
  - `primary_tie_reinforcement`: e.g. "3-N24", "4-N20", "4-N28"
  - `horizontal_stirrups_description`: e.g. "N10 @ 100 CTS", "N12 @ 120"
  - `bearing_pad_type`: ELASTOMERIC_PAD, STEEL_BEARING_PLATE, PTFE_SLIDING_PAD

## 3. Geometric Model
- Corbel insertion point `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_cbn_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering corbel configurations, projection/depth extraction, tie reinforcement, horizontal stirrups, bearing pads, coordinate snapping, dictionary serialization, and customer retention verification.
