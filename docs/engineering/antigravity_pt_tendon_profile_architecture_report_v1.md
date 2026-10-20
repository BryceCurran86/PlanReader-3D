# Architecture Report v1: Source Post-Tensioned Suspended Slab Tendon Profile & Drape Shadow Authority

## 1. Problem Statement & Scope
Post-tensioned (PT) prestressed suspended concrete slabs utilize unbonded or bonded multi-strand flat duct tendons draped in parabolic trajectories between high points over supporting columns/walls and low points at midspan. High and low chair stool heights (measured in mm from slab soffit to tendon centroid) dictate prestressing eccentricities (e), balancing upward equivalent load pressures, and minimum concrete covers. In structural PT layout drawings, parabolic drape profiles and tendon strand groupings (e.g. 4-strand flat duct tendon groups) are often lost in line noise or conflated with standard rebar bottom reinforcement.

This module introduces `SourcePostTensionedSlabTendonProfileShadowAuthority` to extract and validate PT tendon lines, strand counts per duct (3, 4, or 5 x 12.7mm strands), high point chair heights (mm), low point chair heights (mm), inflection point locations, slab thickness (mm), and effective prestress force (kN) strictly in shadow candidate mode.

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
- `PtTendonProfileCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `strand_count`: Number of 12.7mm or 15.2mm prestressing strands per tendon (e.g. 3, 4, 5)
  - `tendon_group_count`: Number of parallel tendons in band
  - `high_point_chair_mm`: Chair height over supports (mm above soffit)
  - `low_point_chair_mm`: Chair height at midspan (mm above soffit)
  - `slab_thickness_mm`: Overall suspended concrete slab thickness (mm)
  - `duct_type`: `FLAT_PLASTIC_CORRUGATED_DUCT`, `FLAT_GALVANIZED_STEEL_DUCT`, `ROUND_MULTI_STRAND_DUCT`
  - `position`: Snapped `(x, y)` coordinate
- `parse_pt_tendon_profile_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourcePostTensionedSlabTendonProfileShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
