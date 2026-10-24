# Architecture Report: Producer-Owned Source Reflected Ceiling Plan (RCP) Regions Shadow Authority (Item 16)

## Executive Summary
This document establishes the architecture for recovering **IPF1, GRID, and CL03 Reflected Ceiling Regions** (`pb_source_rcp_ceiling_region_shadow.py`), resolving Workstream B, Item 16 of the Autonomous Core Accuracy Engineering Mission.

The primary blockers addressed are:
1. **Material Code Conflation:** Reflected ceiling drawings (e.g., Maryborough A120 p9) contain distinct ceiling systems:
   - `IPF1`: 13mm flush-set plasterboard ceiling linings with square-set edges (internal wet areas and amenities, e.g. PWD, AMB, Laundry).
   - `GRID`: Exposed acoustic tile grid ceiling (internal office and dining areas).
   - `CL03` (printed as `CLD3` in contractor drawings): External canopy, eave, and signage fascia cladding.
   Treating external cladding as internal ceiling linings would fabricate invalid interior room areas.
2. **Unsealed RCP Authority:** Previous implementations lacked a sealed lookup authority (`SourceRcpCeilingRegionAuthority`) and did not compute scale-calibrated metric areas (`area_m2`).
3. **Multi-Mark Enclosure Ambiguity:** In unpartitioned spaces, competing finish marks or open-plan boundaries must fail closed (`COMPETING_CEILING_MARKS_IN_ZONE`), preventing ambiguous assignment of ceiling materials without explicit source-drawn dividing bulkheads.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Implements standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons to prevent external tampering or ungrounded synthesis.
- Factory method `SourceRcpCeilingRegionProducer.create()` produces the mutable producer.
- Once evaluated, calling `.authority()` returns an immutable `SourceRcpCeilingRegionAuthority` mapping selectors to results.

### 2. Ceiling Role Segregation Gate
- Segregates material roles into:
  - `ROLE_INTERNAL_CEILING_LINING`: `IPF1`, `GRID`, `PLASTERBOARD`, `ACOUSTIC_TILE`.
  - `ROLE_EXTERNAL_OVERHEAD_CLADDING`: `CL03`, `CLD3`, `STP`, `SOFFIT`, `CANOPY_CLADDING`.
- When querying for internal ceiling linings, any region bounded by or tagged with external cladding (`CL03`/`CLD3`) fails closed with `EXTERNAL_CLADDING_VETOES_INTERNAL_CEILING`.

### 3. Metric Scale Calibration
- When `scale_px_per_m` is supplied from an authenticated scale authority, `area_m2 = area_pts2 / (scale_px_per_m ** 2)`.
- If uncalibrated, `area_m2 = None` and `area_pts2` is retained losslessly.

### 4. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Baseline customer retention hash verified (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
