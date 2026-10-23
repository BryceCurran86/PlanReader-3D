# Architecture Report v1: Source Industrial Concrete Slab Sawcut Dowel Basket Assembly Shadow Authority

## 1. Problem Statement & Scope
Industrial concrete ground slabs and external hardstands rely on prefabricated welded wire dowel baskets (cradles) positioned across sawn contraction joints to ensure horizontal joint expansion/contraction and vertical shear load transfer between adjoining panels without joint stepping or curling. In legacy extractions, dowel basket assemblies were frequently conflated with simple rebar dowels or loose plate dowels, omitting critical basket wire framework details, dowel bar diameters (e.g., R16, R20, R24), de-bonding sleeves, and on-center spacing (typically 300mm–450mm).

This module introduces `SourceSlabDowelBasketAssemblyShadowAuthority` to extract and validate concrete slab dowel basket callouts, dowel bar diameters, lengths, on-center spacing, de-bonding treatments (expansion sleeves vs greased ends), slab thicknesses, and wire frame specifications strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Geometric Snapping**:
   - 2D coordinates snapped using `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Extraction inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000` to prevent memory exhaustion.
4. **Zero Gold Dependencies**:
   - No hardcoded project or sheet heuristics; pure deterministic regex and keyword parsing.
5. **Customer Baseline Invariance**:
   - Preserves SHA-256 `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.

## 3. Authority Interface
- `SlabDowelBasketAssemblyCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `joint_type`: `SAWCUT_CONTRACTION_JOINT`, `INDUCED_CRACK_JOINT`, `LONGITUDINAL_HINGED_JOINT`, `EXPANSION_BASKET_JOINT`
  - `dowel_bar_type`: `ROUND_STEEL_DOWEL_R16`, `ROUND_STEEL_DOWEL_R20`, `ROUND_STEEL_DOWEL_R24`, `SQUARE_DOWEL_BAR`, etc.
  - `dowel_spacing_mm`: Dowel on-center pitch in mm (e.g. 300.0, 450.0)
  - `dowel_length_mm`: Dowel length in mm (e.g. 400.0, 450.0, 500.0)
  - `slab_thickness_mm`: Slab depth in mm (e.g. 150.0, 200.0)
  - `debonding_treatment`: `PLASTIC_EXPANSION_SLEEVE`, `HALF_GREASED_DEBONDED`, `TECTYL_COATED`, `NONE`
  - `position`: Snapped `(x, y)` coordinate
- `parse_slab_dowel_basket_assembly_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceSlabDowelBasketAssemblyShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
