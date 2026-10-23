# Architecture Report: Producer-Owned Source External Soffits and Eaves Shadow Authority (Item 17)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Source External Soffits and Eaves Shadow Authority** (`pb_source_external_soffit_eaves_shadow.py`), resolving Workstream B, Item 17 of the Autonomous Core Accuracy Engineering Mission: "Include external soffits and eaves where measurable."

The primary blockers addressed are:
1. **Misclassification of External Soffits as Internal Ceiling Finishes:** Prior heuristic extractors frequently conflated external soffits and canopy undercladding (e.g. "STP" Stramit Premier 300 Soffit Cladding, "FCS1" Fibre Cement Soffit) with internal room ceiling linings (e.g. "GRID", "IPF1"). This improperly inflated internal ceiling areas and contaminated room takeoff schedules.
2. **Missing Boundary Synthesis for External Overhangs:** External eaves and soffits do not sit within closed four-walled room spaces. Instead, they are bounded between an internal/external wall face edge on one side and an exterior roof fascia/eave line on the other. Without an explicit authority proving this boundary relationship, soffit zones remained unmeasured or dropped as non-room voids.
3. **Producer-Owned Overhang Verification & Metric Calibration:** This module establishes an immutable producer/authority contract that validates 2D closed polygon boundaries, proves exterior wall face anchors, enforces strict material role segregation (`ROLE_EXTERNAL_OVERHEAD_CLADDING` vs `ROLE_INTERNAL_CEILING_LINING`), cross-corroborates figured overhang dimensions against measured polygon widths, and computes scale-calibrated metric areas ($m^2$) and linear perimeters ($lm$).

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceExternalSoffitProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceExternalSoffitAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Soffit & Eaves Geometric Gates
- **2D Closed Polygon Gate:**
  - Evaluates boundary point arrays into Shapely polygons.
  - Degenerate, collinear, or self-intersecting geometries fail with `SOFFIT_INVALID_GEOMETRY` and `SOFFIT_BOUNDARY_NOT_CLOSED`.
- **Wall Face Anchor Gate:**
  - Soffit regions must cite at least one verified external wall face edge (`inner_wall_edge_ids`).
  - Regions floating without an external wall anchor are flagged with `SOFFIT_WALL_FACE_ANCHOR_MISSING`.
- **Strict Role Segregation & Material Veto Gate:**
  - Explicit internal finish codes (e.g. `IPF1`, `GRID`, `CARPET`, `VINYL`, `FT2`, `FT3`) registered as soffits trigger `SOFFIT_INTERNAL_CEILING_CONFLICT` and cause immediate resolution failure (`ABSTAINED`).
  - Accepted soffit/eaves materials (`STP`, `FCS1`, `FC_SOFFIT`, `SOFFIT`, `EAVE`, `EAVES`, `CANOPY_CLADDING`, `COLORBOND_SURFMIST`) are assigned `ROLE_EXTERNAL_OVERHEAD_CLADDING`.
- **Overhang Cross-Corroboration:**
  - Evaluates the short dimension of the soffit polygon as the measured overhang depth ($\text{mm}$).
  - Compares against figured overhang dimensions (e.g. 450 mm, 600 mm) within a $\le 5\%$ tolerance. Discrepancies trigger `SOFFIT_OVERHANG_DISCREPANCY`.
- **Serialised WKB Geometry:**
  - Encodes the complete verified soffit polygon as standard OGC WKB hex.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
