# Antigravity Architecture Report: Fire Protection Wet / Dry Riser Landing Valve & Pressure Restrictor Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for wet and dry riser fire landing valves, pressure restricting orifices (PRO), pressure reducing valves (PRV), and hydrant cabinets from fire protection engineering drawings.

## Scope & Target Geometry
- Identifies fire brigade landing valves located in stairwell dry/wet riser standpipes.
- Classifies valve pattern (oblique, right angle, bib-nose), coupling adapter standard (Storz, BS336 instantaneous, NH thread), pressure regulation mechanism (pressure-reducing valve, restricting orifice plate), and cabinet enclosure mounting.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
