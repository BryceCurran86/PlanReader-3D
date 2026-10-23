# Architecture Report: Source Precast Concrete Core Wall Splice Shoe & NMB Splice Sleeve Shadow Authority (v1)

## Executive Summary
Precast concrete core walls, elevator shafts, and stair shear walls transfer overturning moments, seismic lateral shear, and axial gravity forces across horizontal panel joints. Vertical rebar connections are made either with cast-in bolted wall splice shoes (anchored to baseplates/studs with high-tensile anchor bolts) or grouted rebar splice sleeves (such as NMB splice sleeves or corrugated steel grouted ducts) injected with ultra-high-strength (80-100 MPa) non-shrink cementitious grout.
This report establishes the candidate shadow authority for parsing and extracting precast wall splice shoes, sleeve diameters, bar designations, and joint spacing from structural core wall drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `SPLICE SHOE`, `WALL SHOE`, `NMB SPLICE SLEEVE`, `GROUTED SPLICE SLEEVE`, `PRECAST WALL SPLICE`, `REBAR SPLICE SLEEVE`, `TENSION SPLICE SHOE`.
2. **Key Physical Parameters**:
   - `splice_type`: `BOLTED_WALL_SHOE`, `GROUTED_SPLICE_SLEEVE`, `GROUTED_CORRUGATED_DUCT`, `MECHANICAL_COUPLER`.
   - `bar_size`: Reinforcing bar size (e.g. `N20`, `N24`, `N28`, `N32`, `N36`).
   - `bolt_diameter`: High-strength bolt size (e.g. `M24`, `M30`, `M36`).
   - `grout_strength_mpa`: Grout compressive strength (e.g. `70`, `80`, `100`).
   - `shoe_recess_mm`: Recess / pocket height into wall face.
3. **Geometric Snapping & Polyline Representation**:
   - Joint points and connection array lines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or coordinate span.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
