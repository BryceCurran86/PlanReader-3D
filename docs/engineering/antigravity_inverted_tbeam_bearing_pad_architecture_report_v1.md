# Architecture Report: Source Precast Concrete Inverted T-Beam & Ledger Bearing Pad Shadow Authority (v1)

## Executive Summary
Precast concrete frames utilize inverted T-beams (ITBs) and L-shaped edge ledger beams to support precast floor units (such as hollowcore slabs or prestressed double tees) with reduced total structural floor depth. Floor elements rest on the protruding lower ledges of the beams, cushioned by chloroprene (neoprene) elastomeric bearing pads or continuous strips that accommodate thermal expansion, beam rotation, and shrinkage movements while preventing localized edge spalling.
This report establishes the candidate shadow authority for parsing and extracting inverted T-beam and ledger ledge dimensions, bearing pad specifications, and seating geometry from structural plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `INVERTED T-BEAM`, `INVERTED TEE`, `LEDGER BEAM`, `LEDGE BEAM`, `BEARING PAD`, `NEOPRENE BEARING STRIP`, `ELASTOMERIC BEARING PAD`.
2. **Key Physical Parameters**:
   - `beam_type`: `INVERTED_T_BEAM`, `L_SHAPED_LEDGER_BEAM`, `RECTANGULAR_BEAM`.
   - `web_width_mm`: Width of upper web or total bottom flange.
   - `overall_depth_mm`: Total beam depth (e.g. `600`, `750`, `900`, `1200`).
   - `ledge_width_mm`: Protruding ledge seating width (e.g. `150MM`, `200MM`).
   - `bearing_pad_material`: `CHLOROPRENE_NEOPRENE`, `PTFE_SLIDE_PAD`, `REINFORCED_ELASTOMERIC`.
   - `bearing_pad_thickness_mm`: Pad thickness (e.g. `6MM`, `10MM`, `12MM`, `20MM`).
   - `durometer_hardness`: Hardness rating (e.g. `50`, `60`, `70`).
3. **Geometric Snapping & Polyline Representation**:
   - Beam centerlines, ledge lines, and pad positions snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total beam/ledge length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
