# Antigravity Architecture Report: HVAC VRF / VRV Branch Selector Box & Refnet Joint Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for variable refrigerant flow (VRF/VRV) branch selector boxes (BS boxes / mode control units), Refnet branch joints, and multi-port headers from mechanical HVAC layout drawings.

## Scope & Target Geometry
- Identifies 3-pipe heat recovery branch selector boxes (single-port and multi-port units) and 2-pipe heat pump Refnet branch fittings.
- Classifies port counts (1, 4, 6, 8, 12 ports), system configuration (heat recovery vs heat pump), connected indoor capacity (kW), refrigerant pipe diameters (liquid, low-pressure gas, high-pressure gas), and condensate drain connections.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
