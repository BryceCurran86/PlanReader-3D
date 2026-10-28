# Antigravity Architecture Report: Lightning Protection Air Terminal & Down-Conductor Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for commercial lightning protection systems (LPS), Franklin air terminals, Early Streamer Emission (ESE) ionizing terminals, roof mesh conductors, down-conductor tapes, and earth inspection test wells from electrical and architectural roof plan drawings.

## Scope & Target Geometry
- Identifies roof level lightning strike termination air rods, parapet perimeter tape conductors, and vertical down-conductors per AS 1768 / NFPA 780 / IEC 62305.
- Classifies air terminal height and tip material (copper, stainless, aluminum, ESE), down-conductor profile (e.g. 25x3mm bare copper tape, insulated high-voltage cable), earth disconnect test clamps, and earth rod inspection pits.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
