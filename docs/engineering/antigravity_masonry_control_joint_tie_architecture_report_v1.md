# Architecture Report v1: Source Cavity Masonry Movement Control Joint & Debonded Tie Shadow Authority

## 1. Problem Statement & Scope
Unreinforced and reinforced brick/block masonry walls require vertical expansion and articulation movement control joints (MCJs / EJ) spaced at regular engineering intervals (typically 6m - 8m) to accommodate thermal expansion, brick growth, and differential foundation settlement without cracking. Across cavity articulation joints, shear load transfer and out-of-plane lateral stability require stainless steel slip ties with plastic debonding sleeves, closed-cell polyethylene foam backing rods, and elastomeric joint sealants. In architectural drawings, vertical control joints are frequently conflated with simple vertical hatch dividers or window jamb alignments.

This module introduces `SourceMasonryControlJointTieShadowAuthority` to extract and validate masonry vertical control joints, joint widths (10mm - 20mm), debonded slip tie types (stainless steel flat / wire / triangular), tie vertical spacing (300mm - 600mm), backing rod diameters, and polyurethane sealant classifications strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Geometric Snapping**:
   - Snapped with `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
4. **Zero Gold Dependencies**:
   - Pure regex and keyword parsing without benchmark gold dependencies.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `MasonryControlJointTieCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `joint_width_mm`: Vertical movement joint gap width (mm)
  - `tie_type`: `DEBONDED_SLIP_TIE_WITH_SLEEVE`, `EXPANSION_TIE_STAINLESS_STEEL`, `DOVETAIL_DEBONDED_ANCHOR`
  - `tie_vertical_spacing_mm`: Center-to-center vertical pitch of ties (mm)
  - `sealant_type`: `POLYURETHANE_ELASTOMERIC_SEALANT`, `LOW_MODULUS_SILICONE`, `HYBRID_POLYMER`
  - `backing_rod_diameter_mm`: Closed-cell polyethylene backing rod diameter (mm)
  - `position`: Snapped `(x, y)` coordinate
- `parse_masonry_control_joint_tie_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceMasonryControlJointTieShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
