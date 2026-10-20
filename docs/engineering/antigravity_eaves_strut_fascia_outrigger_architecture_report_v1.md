# Architecture Report: Source Structural Steel Purlin Eaves Strut & Fascia Girt Outrigger Shadow Authority (v1)

## Executive Summary
In structural portal frame and industrial shed framing, the intersection between the wall framing and roof framing at the eaves requires specialized transition members: eaves struts (resisting axial wind loads and supporting roof sheeting) and cantilever fascia girt outriggers (supporting fascia cladding and box/eaves gutters).
This report documents the candidate shadow authority for parsing and extracting eaves strut and fascia outrigger geometry from source structural engineering plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `EAVES STRUT`, `EAVE STRUT`, `FASCIA GIRT`, `EAVES BEAM`, `FASCIA OUTRIGGER`, `EAVES PURLIN`, `EAVE GUTTER OUTRIGGER`.
2. **Key Physical Parameters**:
   - `member_type`: `EAVES_STRUT`, `FASCIA_GIRT`, `OUTRIGGER_BRACKET`, `EAVES_BEAM`.
   - `section_profile`: Cold-formed C/Z or hollow section (e.g. `C20019`, `Z15015`, `C25024`, `100x50x4 RHS`).
   - `outrigger_spacing_mm`: Spacing along rafter/eaves (e.g. `1200 CTS`).
   - `outrigger_length_mm`: Cantilever projection distance (e.g. `600MM PROJECTION`).
   - `connection_type`: `CLEATED_TO_RAFTER`, `STUB_OUTRIGGER_BOLTED`, `CUSTOM_BRACKET`.
3. **Geometric Snapping & Polyline Representation**:
   - Snaps points within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total member line length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
