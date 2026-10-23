# Antigravity Architecture Report: Hydronic Underfloor Heating Manifold & Actuated Circuit Loop Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for hydronic underfloor/in-slab radiant heating and cooling distribution manifolds, actuated circuit loops, thermostatic mixing stations, and recessed enclosures from mechanical HVAC and plumbing drawings.

## Scope & Target Geometry
- Identifies hydronic radiant floor heating/cooling distribution manifolds and circuit headers.
- Classifies loop/port count (e.g. 4 to 12 ports), circuit pipe specification (16mm/20mm PEX-a, PE-RT), electro-thermal actuator control voltage (24V/230V), flow meter visual balancing indicators, and mixing shunt stations.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
