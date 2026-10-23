# Antigravity Architecture Report: Precast Concrete Stair Flight & Rebated Landing Bearing Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for structural precast concrete stair flights, rebated landing nib bearings, acoustic vibration isolation bearing strips, and cast-in shear dowel connections from structural precast and architectural drawings.

## Scope & Target Geometry
- Identifies precast concrete stair flight components, step rise/going counts and dimensions, and clear stair flight widths.
- Classifies landing bearing details: rebated nib seats, acoustic isolation strips (Sylomer/elastomeric pads), and locating dowel pin sleeve connections.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
