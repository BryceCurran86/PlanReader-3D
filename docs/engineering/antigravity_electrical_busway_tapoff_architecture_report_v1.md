# Architecture Report: Source Electrical Busway Trunking & Tap-Off Plug Unit Shadow Authority (v1)

## Executive Summary
Large commercial developments, manufacturing plants, and mission-critical data centres utilize insulated sandwich busway and busduct trunking systems to distribute high-current power. Feeder busways supply main switchboards, while plug-in busways incorporate tap-off units equipped with moulded case circuit breakers (MCCBs) or fused switches.
This report establishes the candidate shadow authority for parsing and extracting busway trunking routes, tap-off unit locations, and electrical parameters from electrical engineering drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `BUSWAY`, `BUSDUCT`, `BUS TRUNKING`, `TAP-OFF UNIT`, `PLUG-IN UNIT`, `POWER BUSWAY`, `SANDWICH BUSWAY`.
2. **Key Physical Parameters**:
   - `system_type`: `FEEDER_BUSWAY`, `PLUG_IN_BUSWAY`, `TAP_OFF_UNIT`, `EXPANSION_JOINT`.
   - `rating_amperes`: Current rating in amperes (e.g. `800A`, `1000A`, `1600A`, `2500A`, `4000A`).
   - `conductor_material`: `COPPER`, `ALUMINIUM`.
   - `poles_count`: `3P`, `4P`, `3P+N+E`.
   - `enclosure_ip_rating`: `IP54`, `IP55`, `IP65`, `IP66`.
3. **Geometric Snapping & Polyline Representation**:
   - Trunking centerlines and tap-off unit points snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total trunking route length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
