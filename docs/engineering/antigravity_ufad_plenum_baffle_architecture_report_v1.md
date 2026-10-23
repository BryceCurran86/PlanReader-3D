# Architecture Report: Source Underfloor Air Distribution (UFAD) Plenum Baffle & Pressurization Partition Shadow Authority (v1)

## Executive Summary
Commercial offices and data facilities implementing Underfloor Air Distribution (UFAD) or raised access floor air delivery systems rely on a pressurized subfloor void. To maintain balanced air distribution, prevent air leakage between thermal zones, and eliminate acoustic crosstalk beneath partition walls, sheet metal baffles and acoustic barrier boards sealed with continuous closed-cell neoprene gaskets are anchored between the slab and raised floor pedestals.
This report establishes the candidate shadow authority for parsing and extracting UFAD plenum baffle geometry, pressure zoning lines, and acoustic barrier details from mechanical and architectural drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `UFAD PLENUM BAFFLE`, `UNDERFLOOR AIR BAFFLE`, `PLENUM PARTITION`, `PRESSURIZATION BAFFLE`, `SUBFLOOR AIR BARRIER`, `UFAD ZONE DIVIDER`, `UNDERFLOOR ACOUSTIC BARRIER`.
2. **Key Physical Parameters**:
   - `baffle_type`: `AIR_PRESSURE_BAFFLE`, `THERMAL_ZONE_DIVIDER`, `ACOUSTIC_PLENUM_BARRIER`, `FIRE_SMOKE_STOP`.
   - `material`: `GALVANIZED_SHEET_STEEL`, `MINERAL_FIBRE_BOARD`, `CALCIUM_SILICATE`, `GYPSUM_BOARD`.
   - `height_mm`: Plenum void depth / baffle height (e.g. `200`, `300`, `450`, `600`).
   - `gasket_seal`: `NEOPRENE_FOAM`, `INTUMESCENT_MASTIC`, `ACOUSTIC_SEALANT`.
   - `differential_pressure_pa`: Static pressure rating (e.g. `12.5 Pa`, `25 Pa`, `50 Pa`).
3. **Geometric Snapping & Polyline Representation**:
   - Baffle lines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total linear baffle run.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
