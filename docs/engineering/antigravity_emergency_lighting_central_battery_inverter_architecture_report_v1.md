# Antigravity Architecture Report: Emergency Lighting Central Battery System & Static Inverter Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for emergency escape lighting central battery systems (CBS), static inverter cubicles, modular battery racks, and addressable emergency monitoring panels from electrical and fire life safety drawings.

## Scope & Target Geometry
- Identifies central battery systems and static inverters feeding emergency exit luminaires and escape route lighting.
- Classifies power capacity (kVA/kW), emergency autonomy duration (e.g. 90min, 120min, 180min), battery chemistry (VRLA, LiFePO4, NiCd), output phase/voltage (230V single phase or 400V 3-phase), and automated DALI addressable testing compliance.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
