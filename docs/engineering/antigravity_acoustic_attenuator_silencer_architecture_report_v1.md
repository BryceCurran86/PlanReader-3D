# Antigravity Architecture Report: HVAC Ductwork In-Line Sound Attenuator Silencer Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for HVAC in-line duct sound attenuators, acoustic silencers, and cross-talk baffles from mechanical ventilation plans.

## Scope & Target Geometry
- Identifies rectangular and circular duct silencers and cross-talk attenuators.
- Classifies duct dimensions (width x height or diameter), active length (e.g. 900mm, 1200mm, 1500mm), system service (supply, return, exhaust, relief), and acoustic media construction (dissipative, packless, hygienic Mylar).
- Extracts acoustic insertion loss tags and casing pressure rating standards.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
