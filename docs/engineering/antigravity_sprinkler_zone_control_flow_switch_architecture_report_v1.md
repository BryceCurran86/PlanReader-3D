# Antigravity Architecture Report: Fire Sprinkler Floor Zone Control Valve & Waterflow Detector Switch Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for wet fire sprinkler floor zone control valve assemblies (ZCV / ZCA), vane-type waterflow detector switches (WFD), monitored supervisory tamper switches, and combination test and drain valves from fire protection engineering drawings.

## Scope & Target Geometry
- Identifies floor-by-floor fire sprinkler zone control riser takeoffs and branch isolations.
- Classifies pipe nominal diameter (DN50 to DN200), isolation valve type (monitored gear-operated wafer/lug butterfly valve or OS&Y gate valve), supervisory tamper switch monitoring, vane-type waterflow switch with pneumatic/electronic retard delay, and inspector test & drain orifice fittings.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
