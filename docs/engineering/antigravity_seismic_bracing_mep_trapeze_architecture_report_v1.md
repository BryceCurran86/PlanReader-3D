# Antigravity Architecture Report: Seismic Bracing for Suspended MEP Services & Trapeze Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for seismic restraint sway bracing systems, rigid strut braces, aircraft cable sway restraints, and trapeze hanger assemblies for suspended mechanical ducts, pipe racks, and electrical cable trays from structural and building services drawings.

## Scope & Target Geometry
- Identifies seismic restraints on suspended non-structural building services per AS 1170.4 / NZS 4219 / SMACNA / ASCE 7.
- Classifies brace orientation (transverse, longitudinal, 4-way), bracing mechanism (rigid unistrut vs tension-only cable sway brace), drop rod diameter (M10-M16), strut channel size (41x41, 41x21), and supported service category (duct, pipe, cable tray, busduct).

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
