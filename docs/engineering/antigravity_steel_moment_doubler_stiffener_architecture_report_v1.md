# Architecture Report: Source Structural Steel Moment Connection Web Doubler Plate & Continuity Stiffener Shadow Authority (v1)

## 1. Context & Authority Scope
- **Domain**: Structural steel connections (AISC 360 / AISC 358 / AS 4100), moment-resisting frames (SMF / IMF / OMF).
- **Subsystem**: Column panel zone web doubler plates, continuity stiffeners (flange-aligned transverse plates), and welding specifications.
- **Authority Type**: Shadow candidate extraction authority (`pb_source_steel_moment_doubler_stiffener_shadow.py`).
- **Safety / Baseline Invariance**:
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - Global snap tolerance: `SNAP_TOLERANCE_PT = 2.5`
  - Safety cap: `MAX_PRIMITIVES_SAFETY_CAP = 20000`
  - Customer retention baseline: byte-for-byte SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 2. Evidence Extraction Specification
- **Callout Pattern Triggers**:
  - `WEB DOUBLER`, `DOUBLER PLATE`, `CONTINUITY STIFFENER`, `MOMENT CONNECTION STIFFENER`, `PANEL ZONE DOUBLER`, `COLUMN STIFFENER PL`.
- **Doubler Configuration**:
  - `SINGLE_DOUBLER` (one side of column web)
  - `DOUBLE_DOUBLER` (both sides of column web)
  - `NONE` (continuity stiffeners only)
- **Extracted Attributes**:
  - `doubler_thickness_mm`: e.g. 10mm, 12mm, 16mm, 20mm
  - `continuity_stiffener_thickness_mm`: e.g. 12mm, 16mm, 20mm, 25mm
  - `continuity_stiffener_pairs`: 1 pair (top or bottom), 2 pairs (both flanges)
  - `weld_type`: CJP_GROOVE, BEVEL_GROOVE, FILLET_WELD
  - `weld_size_mm`: e.g. 8mm, 10mm fillet or full penetration CJP

## 3. Geometric Model
- Connection node point `(x, y)` snapped to 2.5 pt tolerance.
- Candidate ID pattern: `{sheet_id}_mds_{index:03d}`.

## 4. Test Strategy
- 21+ unit tests covering doubler side detection, thickness extraction, continuity stiffener pairs, weld sizing, point snapping, dictionary export, and customer retention verification.
