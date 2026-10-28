# Antigravity Architecture Report: Emergency Exit Photoluminescent & Egress Signage Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for photoluminescent exit signage, self-luminous tritium directional markers, running man exit signs, and escape path safety markings from architectural, life safety, and electrical drawings.

## Scope & Target Geometry
- Identifies photoluminescent and self-luminous emergency exit signs and directional egress route markers.
- Classifies technology (photoluminescent Class A-D, self-luminous, LED hybrid), directional arrow orientation (left, right, straight, double-sided), maximum viewing distance (16m, 24m, 32m), and mounting bracket configuration (wall flush, ceiling suspended, flag mounted).

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
