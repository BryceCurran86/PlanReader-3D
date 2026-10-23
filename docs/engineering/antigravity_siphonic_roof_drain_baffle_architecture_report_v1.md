# Architecture Report: Source Stormwater Siphon Roof Drainage Primus Baffle & Air Baffle Shadow Authority (Item 216 / Blocker 156)

## 1. Executive Summary
Commercial and industrial warehouse roofing, wide-span logistics facilities, and large institutional roofs frequently implement siphonic roof drainage systems (e.g. Pluvia, FastFlow). Unlike gravity drainage, siphonic outlets incorporate engineered air baffles (primus baffles, anti-vortex induction plates) that purge air ingress during heavy rainfall to achieve negative pressure, full-bore cavitation-free hydraulic flow. Hydraulic drawings specify outlet flow rates (L/s), tailpipe diameters (HDPE DN50 to DN160), leaf/gravel grates, and membrane clamping flanges.

This shadow authority extracts and validates siphonic roof drainage baffle and outlet callouts and coordinates strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Hydraulic plumbing drawings, roof drainage plans, siphonic stormwater schematics, and roof penetration schedules.
- **First Failing Authority:** Downstream drainage and plumbing parsers classify siphonic outlets as generic gravity roof sumps, dropping anti-vortex air baffle indicators, siphonic design flow rates (L/s), metric HDPE tailpipe dimensions, leaf guard collars, and secondary overflow designations.

## 3. Data Model & Extraction Capabilities
- `SiphonicRoofDrainBaffleCallout`:
  - `raw_text`: Original unedited callout string.
  - `outlet_type`: `SIPHONIC_OUTLET_PRIMUS_BAFFLE`, `ANTI_VORTEX_AIR_PLATE`, `PARAPET_SCUPPER_SIPHON_OUTLET`, `GUTTER_SUMP_SIPHON_DRAIN`, `GENERIC_SIPHONIC_DRAIN`.
  - `baffle_material`: `STAINLESS_STEEL_316`, `CAST_ALUMINUM`, `UV_STABILIZED_POLYPROPYLENE`, `UNSPECIFIED`.
  - `design_flow_lps`: Extracted siphonic design flow rate in L/s.
  - `tailpipe_dn`: Extracted nominal diameter (e.g., `DN50`, `DN75`, `DN90`, `DN110`, `DN125`, `DN160`).
  - `grate_guard_type`: `LEAF_GUARD_BASKET`, `GRAVEL_GRATE_COLLAR`, `FLAT_TERRACE_GRATE`, `UNSPECIFIED`.
  - `membrane_flange_connection`: `STAINLESS_CLAMPING_FLANGE`, `EPDM_WATERPROOFING_COLLAR`, `BITUMINOUS_FLANGE`, `UNSPECIFIED`.
  - `drainage_system`: `SIPHONIC_STORMWATER`, `SECONDARY_OVERFLOW_SIPHON`.
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
