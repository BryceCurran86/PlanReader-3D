# Architecture Report: Source Structural Steel Rafter Knee Haunch Stiffener Plate Shadow Authority (Item 215 / Blocker 155)

## 1. Executive Summary
Portal frame industrial sheds and warehouse buildings rely on moment-resisting knee joints at the junction between vertical columns and pitched roof rafters. The knee haunch—fabricated by cutting and tapering a matching universal beam (UB) section welded to the rafter bottom flange—is reinforced by transverse column web stiffener plates, diagonal knee stiffeners, flange doublers, full penetration butt welds, and high-strength structural bolt groups (e.g. M24 / M30 Gr 8.8).

This shadow authority extracts and validates structural steel rafter knee haunch and stiffener plate callouts and geometries strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Structural steel general arrangement drawings, portal frame connection details, shop drawing fabrication details, and moment connection schedules.
- **First Failing Authority:** Downstream framing and takeoff parsers interpret rafters and columns as simple intersecting axial centerlines without haunch tapering, omitting moment-capacity haunch geometries, stiffener plate thicknesses (12mm–25mm), weld designations (FPBW / fillet), and high-strength bolt groups.

## 3. Data Model & Extraction Capabilities
- `SteelKneeHaunchStiffenerCallout`:
  - `raw_text`: Original unedited callout string.
  - `haunch_type`: `TAPERED_CUT_BEAM_HAUNCH`, `FABRICATED_PLATE_HAUNCH`, `FLANGE_DOUBLER_HAUNCH`, `GENERIC_KNEE_HAUNCH`.
  - `stiffener_plate_thickness_mm`: Stiffener plate thickness (e.g., 10mm, 12mm, 16mm, 20mm, 25mm).
  - `haunch_depth_mm`: Overall depth of haunch at column face (e.g., 500mm, 600mm, 800mm).
  - `haunch_length_mm`: Length of haunch along rafter (e.g., 1000mm, 1200mm, 1500mm).
  - `bolt_specification`: Extracted structural bolt group (e.g., `8-M24 8.8/S`, `M30 GR 8.8`).
  - `weld_specification`: Extracted weld callout (e.g., `8MM CFW`, `FPBW`, `10MM FILLET`).
  - `stiffener_orientation`: `DIAGONAL_KNEE_STIFFENER`, `TRANSVERSE_COLUMN_STIFFENER`, `WEB_CONTINUITY_STIFFENER`, `UNSPECIFIED`.
  - `portal_member_section`: Extracted UB or UC section (e.g., `530UB82`, `460UB74`, `310UC96`).
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
