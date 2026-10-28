# Antigravity Architecture Report: Stormwater Gross Pollutant Trap & CDS Unit Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for civil stormwater gross pollutant traps (GPT), continuous deflective separation (CDS) units, hydrodynamic vortex separators, and catch basin drop-in baskets from civil drainage engineering drawings.

## Scope & Target Geometry
- Identifies stormwater quality improvement devices (SQIDs), gross pollutant traps, CDS hydrodynamic vortex units, and inline/offline pollutant interceptor chambers.
- Classifies treatable design flow rate (L/s), connected storm pipe nominal diameter (DN225 to DN1200), sediment sump volume (m3), screen aperture size (e.g. 1.2mm, 2.4mm, 4.7mm), internal weir bypass configuration, and cover load ratings (Class B/D).

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
