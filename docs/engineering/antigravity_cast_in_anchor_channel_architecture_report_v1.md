# Architecture Report: Source Cast-in Concrete Wall Anchor Channel Embed Cold-Formed Channel Shadow Authority (Item 219 / Blocker 159)

## 1. Executive Summary
Cast-in-place concrete structures and architectural precast facades incorporate embedded cast-in anchor channels (e.g., Halfen HTA, Hilti HAC, Jordahl, Ancon) flush-mounted to concrete surfaces (walls, columns, slab edges, beams). These cold-formed or hot-rolled C-channels feature integral welded round-head stud anchors or forged I-anchors that transfer tensile and shear forces from curtain wall transoms, precast spandrels, elevator guide rails, and heavy MEP services directly into structural concrete without post-drilled anchors.

This shadow authority extracts and validates cast-in anchor channel callouts, series designations, lengths, finishes, and attachment applications strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Structural concrete drawings, facade/curtain wall anchorage details, precast concrete shop drawings, and elevator shaft connection sections.
- **First Failing Authority:** Downstream wall framing and concrete parsers treat channel embed lines as superficial cosmetic linework or omit them entirely, causing missed edge clearances, clashes with post-tensioning anchors, and loss of cast-in channel lengths and series specifications.

## 3. Data Model & Extraction Capabilities
- `CastInAnchorChannelCallout`:
  - `raw_text`: Original unedited callout string.
  - `channel_profile`: `COLD_FORMED_ANCHOR_CHANNEL`, `HOT_ROLLED_ANCHOR_CHANNEL`, `TOOTHED_SERRATED_CHANNEL`, `SLAB_EDGE_FACIA_CHANNEL`, `GENERIC_ANCHOR_CHANNEL`.
  - `channel_series`: Extracted model/series designation (e.g. `HAC-50`, `HTA-52/34`, `HTA-40/22`, `HAC-40`).
  - `channel_length_mm`: Extracted channel length in mm (e.g., 200mm, 250mm, 300mm, 350mm, 1050mm).
  - `anchor_stud_type`: `ROUND_HEAD_STUD_ANCHOR`, `I_STUD_FORGED_ANCHOR`, `END_LUG_ANCHOR`, `WELDED_STUD`, `UNSPECIFIED`.
  - `material_finish`: `HOT_DIP_GALVANIZED_STEEL`, `STAINLESS_STEEL_A4_316`, `CARBON_STEEL_MILL_FINISH`, `UNSPECIFIED`.
  - `filler_type`: `CLOSED_CELL_FOAM_STRIP`, `PE_PLASTIC_FILLER`, `COMB_FOAM_FILLER`, `UNSPECIFIED`.
  - `structural_application`: `CURTAIN_WALL_BRACKET`, `ELEVATOR_GUIDE_RAIL`, `PRECAST_CLADDING_FACADE`, `MEP_PIPE_SUPPORT`, `GENERIC_EMBED_CONNECTION`.
  - `position`: Snapped `(x, y)` coordinate.
  - `status`: Constant `"CANDIDATE"`.
  - `commercial_projection_allowed`: Constant `False`.
  - `takeoff_eligible`: Constant `False`.
  - `metadata`: Supplemental dictionary.

## 4. Invariants & Safety
- Strict shadow candidate isolation: no commercial projection or takeoff eligibility.
- Global 2.5 pt coordinate snapping (`SNAP_TOLERANCE_PT = 2.5`).
- Maximum 20,000 primitive safety cap (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
- Customer retention baseline verification: byte-for-byte invariance maintained on `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
