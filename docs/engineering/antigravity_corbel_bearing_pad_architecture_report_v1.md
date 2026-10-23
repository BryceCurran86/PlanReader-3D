# Architecture Report v1: Source Precast Concrete Corbel & Elastomeric Bearing Pad Shadow Authority

## 1. Problem Statement & Scope
Precast concrete structural systems rely on monolithic cast column corbels or wall brackets equipped with elastomeric bearing strips/pads (chloroprene / neoprene) to transfer heavy shear reactions from precast prestressed beams, double-T slabs, or bridge planks while accommodating rotation and shrinkage movement. In structural drawing annotations, corbels and bearing pads are often lost in line junctions or misclassified as standard column wall faces.

This module introduces `SourceCorbelBearingPadShadowAuthority` to extract and validate precast concrete corbels, bearing pad dimensions (length x width x thickness mm), elastomer elastomer durometer (Shore A 50-70), design vertical load capacity (kN), and steel shim plate reinforcement strictly in shadow candidate mode.

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
- `CorbelBearingPadCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `corbel_projection_mm`: Corbel cantilever projection from column face (mm)
  - `corbel_depth_mm`: Overall vertical corbel depth (mm)
  - `bearing_pad_material`: `PLAIN_ELASTOMERIC_NEOPRENE_PAD`, `STEEL_REINFORCED_LAMINATED_BEARING`, `PTFE_SLIDING_PAD`
  - `pad_thickness_mm`: Thickness of bearing strip/pad (mm)
  - `shore_a_hardness`: Durometer hardness (e.g. 50, 60, 70)
  - `design_shear_kn`: Rated vertical design shear load capacity (kN)
  - `position`: Snapped `(x, y)` coordinate
- `parse_corbel_bearing_pad_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceCorbelBearingPadShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
