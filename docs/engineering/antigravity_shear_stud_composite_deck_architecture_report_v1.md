# Architecture Report v1: Source Headed Concrete Shear Stud & Composite Decking Shadow Authority

## 1. Problem Statement & Scope
Composite steel-concrete floor systems require headed shear connector studs (Nelson studs) welded through profiled galvanized steel composite decking (e.g. Bondek, Condeck, KingFlor, ComFlor) onto structural steel composite beams to transfer longitudinal horizontal shear forces and achieve full or partial composite flexural beam action. In structural steel framing plans and composite slab schedules, shear stud quantities and profile decking rib pitches (typically 1 stud or 2 studs per pan / rib) are frequently omitted or conflated with standard field bolts.

This module introduces `SourceShearStudCompositeDeckShadowAuthority` to extract and validate headed concrete shear studs, stud dimensions (diameter x length e.g. 19x100mm, 19x125mm), studs per rib/pan (1 or 2), composite steel decking profile types, steel sheet base metal thickness (BMT 0.75mm - 1.2mm), and shear transfer capacity (kN) strictly in shadow candidate mode.

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
- `ShearStudCompositeDeckCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `stud_diameter_mm`: Nominal stud shank diameter (e.g. 19.0, 22.0 mm)
  - `stud_length_mm`: Stud length after burn-off / weld (e.g. 100.0, 125.0 mm)
  - `studs_per_trough`: Count of studs per deck pan/rib (e.g. 1, 2)
  - `decking_profile`: `PROFILED_COMPOSITE_STEEL_DECKING_BONDEK`, `CONDECK_HP_PROFILE`, `DOVETAIL_RE-ENTRANT_DECKING`
  - `deck_bmt_mm`: Sheet steel base metal thickness (mm)
  - `characteristic_shear_kn`: Nominal stud shear strength in concrete slab (kN)
  - `position`: Snapped `(x, y)` coordinate
- `parse_shear_stud_composite_deck_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceShearStudCompositeDeckShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
