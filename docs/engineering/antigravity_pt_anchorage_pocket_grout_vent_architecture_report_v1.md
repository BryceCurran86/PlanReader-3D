# Architecture Report: Source Post-Tensioned Concrete Anchorage Pocket & Grout Vent Shadow Authority (v1)

## Executive Summary
Post-tensioned (PT) concrete slabs, transfer plates, and band beams utilize high-strength steel prestressing strands tensioned against edge anchorages. Live-end stressing anchorages are cast into edge blockouts (stressing pockets) that are later backfilled with non-shrink structural grout or protective epoxy mortar. High-point grout vent tubes and low-point drainage ports penetrate the slab surface to ensure complete encapsulation of bonded tendons with cementitious grout.
This report establishes the candidate shadow authority for parsing and extracting PT anchorage pocket blockouts, strand capacities, and grout vent locations from structural post-tensioning drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `POST-TENSIONED`, `PT ANCHORAGE`, `STRESSING POCKET`, `GROUT VENT`, `LIVE END ANCHORAGE`, `DEAD END ANCHORAGE`, `TENDON DUCT VENT`.
2. **Key Physical Parameters**:
   - `anchorage_type`: `LIVE_END_STRESSING`, `DEAD_END_FIXED`, `INTERMEDIATE_COUPLER`, `GROUT_VENT_POINT`.
   - `strand_count`: Number of 7-wire strands in tendon (e.g. `1`, `4`, `5`, `7`, `12`, `19`).
   - `strand_diameter_mm`: Strand diameter (typically `12.7MM` or `15.2MM`).
   - `pocket_recess_mm`: Recess depth into slab edge (e.g. `75MM`, `100MM`, `125MM`).
   - `grout_vent_type`: `HIGH_POINT_VENT`, `LOW_POINT_DRAIN`, `INTERMEDIATE_VENT`.
3. **Geometric Snapping & Representation**:
   - Anchor locations and vent points snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or coordinate span.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
