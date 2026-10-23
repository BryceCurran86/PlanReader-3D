# Architecture Report v1: Source Structural Steel Cast-In Anchor Bolt & Embedment Shadow Authority

## 1. Problem Statement & Scope
Structural steel column bases and portal frame uprights require heavy-duty cast-in anchor bolt assemblies embedded into reinforced concrete footings, grade beams, or pedestals. In structural steel and foundation plan drawings, cast-in anchor bolts are often conflated with post-installed chemical anchors, mechanical sleeve studs, or simple baseline dots.

This module introduces `SourceCastInAnchorBoltEmbedmentShadowAuthority` to extract and validate cast-in anchor bolt patterns, bolt grades (Grade 8.8, Grade 4.6), thread diameters (M16 - M36), effective embedment depths (mm), bottom anchor plates/washers, and bolt configurations (cogged L-bolt, J-bolt, headed stud) strictly in shadow candidate mode.

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
   - Deterministic regex and token parsing without benchmark-specific biases.
5. **Customer Baseline Invariance**:
   - Preserves complete isolation from customer gold baselines.

## 3. Authority Interface
- `CastInAnchorBoltEmbedmentCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `bolt_grade`: Steel grade (e.g. `GRADE_8_8_HIGH_TENSILE`, `GRADE_4_6_COMMERCIAL`)
  - `thread_size`: Nominal metric thread (e.g. `M20`, `M24`, `M30`, `M36`)
  - `bolt_count`: Number of bolts in group (e.g. 2, 4, 6, 8)
  - `embedment_depth_mm`: Effective embedment depth in concrete (mm)
  - `anchor_termination`: `HEAVY_HEX_NUT_AND_SQUARE_PLATE_WASHER`, `COGGED_L_HOOK`, `J_BOLT_HOOK`
  - `projection_above_top_of_concrete_mm`: Projection height (mm)
  - `position`: Snapped `(x, y)` coordinate
- `parse_cast_in_anchor_bolt_embedment_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceCastInAnchorBoltEmbedmentShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
